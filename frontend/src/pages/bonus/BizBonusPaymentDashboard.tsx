/**
 * 业务奖金流转单支付情况 — 对齐简道云 commission_database 仪表盘 v1/v2。
 * v1：可修改（跳转提成数据库编辑支付状态子表）
 * v2：只读 + 业务员/合同号透视汇总
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Card, DatePicker, Flex, Input, Select, Space, Table, Tag, Typography, Spin, message,
} from 'antd'
import {
  ArrowLeftOutlined, EditOutlined, ReloadOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { lowcodeApi } from '@/api/lowcode'
import type { FormInstance } from '@/types/lowcode'
import DepartmentSelect from '@/components/DepartmentSelect'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import type { FormFilterDsl } from '@/components/lowcode/formInstanceFilterUtils'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'

const { Title, Text } = Typography
const { RangePicker } = DatePicker

type DashboardMode = 'v1' | 'v2'

type PaymentLine = {
  field_5?: string
  field_6?: number
  field_7?: string
}

type PivotRow = {
  key: string
  salesperson: string
  department: string
  company: string
  contractNo: string
  payable: number
  paid: number
  unpaid: number
  payRatio: number | null
}

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  submitted: { color: 'blue', text: '已提交' },
  running: { color: 'gold', text: '审批中' },
  completed: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
  withdrawn: { color: 'default', text: '已撤回' },
}

const LIST_COLUMNS = [
  'bonus_no', 'commission_date', 'company_name', 'salesperson', 'department',
  'contract_no', 'contract_amount', 'current_bonus', 'field_9',
] as const

const COL_LABELS: Record<string, string> = {
  bonus_no: '奖金编号',
  commission_date: '提成日期',
  company_name: '单位名称',
  salesperson: '业务员',
  department: '部门',
  contract_no: '合同号',
  contract_amount: '合同金额',
  current_bonus: '本次奖金金额',
  field_9: '已支付金额',
}

function defaultYearRange(): [Dayjs, Dayjs] {
  return [dayjs().startOf('year'), dayjs().endOf('year')]
}

function buildFilters(
  contractNo: string,
  salespersonId: string | undefined,
  departmentId: string | undefined,
  companyName: string,
  bonusNo: string,
  dateRange: [Dayjs, Dayjs] | null,
): FormFilterDsl {
  const rules: FormFilterDsl['rules'] = []
  const cn = contractNo.trim()
  if (cn) rules.push({ field: 'contract_no', op: 'contains', value: cn })
  if (salespersonId) rules.push({ field: 'salesperson', op: 'eq', value: salespersonId })
  if (departmentId) rules.push({ field: 'department', op: 'eq', value: departmentId })
  const comp = companyName.trim()
  if (comp) rules.push({ field: 'company_name', op: 'contains', value: comp })
  const bn = bonusNo.trim()
  if (bn) rules.push({ field: 'bonus_no', op: 'contains', value: bn })
  const dr = dateRange || defaultYearRange()
  rules.push({
    field: 'commission_date',
    op: 'between',
    value: [dr[0].format('YYYY-MM-DD'), dr[1].format('YYYY-MM-DD')],
  })
  return { match: 'all', rules }
}

function fmtMoney(v: unknown) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0.00'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(v: number | null) {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(2)}%`
}

function refId(val: unknown): string {
  if (val == null || val === '') return ''
  if (typeof val === 'object' && val && 'id' in val) return String((val as { id: string }).id)
  return String(val)
}

function paidAmount(fd: Record<string, unknown>): number {
  const top = Number(fd.field_9)
  if (Number.isFinite(top) && top > 0) return top
  const lines = (fd.payment_status || []) as PaymentLine[]
  if (!Array.isArray(lines)) return 0
  return lines.reduce((s, row) => s + (Number(row.field_6) || 0), 0)
}

function payableAmount(fd: Record<string, unknown>): number {
  return Number(fd.current_bonus) || 0
}

function cellText(
  field: string,
  val: unknown,
  maps: { dept: Record<string, string>; person: Record<string, string> },
) {
  if (val == null || val === '') return '—'
  if (field === 'department') {
    const id = refId(val)
    return maps.dept[id] || id
  }
  if (field === 'salesperson') {
    const id = refId(val)
    return maps.person[id] || id
  }
  if (field === 'commission_date') {
    const s = String(val)
    return s.length >= 10 ? s.slice(0, 10) : s
  }
  if (field === 'contract_amount' || field === 'current_bonus' || field === 'field_9') {
    return fmtMoney(val)
  }
  return String(val)
}

function buildPivotRows(items: FormInstance[], maps: { dept: Record<string, string>; person: Record<string, string> }): PivotRow[] {
  const bucket = new Map<string, PivotRow>()
  for (const inst of items) {
    const fd = inst.form_data || {}
    const spId = refId(fd.salesperson)
    const deptId = refId(fd.department)
    const company = String(fd.company_name || '')
    const contractNo = String(fd.contract_no || '')
    const key = `${spId}|${deptId}|${company}|${contractNo}`
    const cur = bucket.get(key) || {
      key,
      salesperson: maps.person[spId] || spId || '—',
      department: maps.dept[deptId] || deptId || '—',
      company,
      contractNo,
      payable: 0,
      paid: 0,
      unpaid: 0,
      payRatio: null,
    }
    cur.payable += payableAmount(fd)
    cur.paid += paidAmount(fd)
    bucket.set(key, cur)
  }
  return [...bucket.values()].map((r) => {
    const unpaid = r.payable - r.paid
    const payRatio = r.payable > 0 ? r.paid / r.payable : null
    return { ...r, unpaid, payRatio }
  }).sort((a, b) => b.unpaid - a.unpaid || a.contractNo.localeCompare(b.contractNo))
}

function aggregateBySalesperson(rows: PivotRow[]) {
  const bucket = new Map<string, PivotRow>()
  for (const r of rows) {
    const key = `${r.salesperson}|${r.department}|${r.company}|${r.contractNo}`
    const cur = bucket.get(key) || { ...r, key, payable: 0, paid: 0, unpaid: 0, payRatio: null }
    cur.payable += r.payable
    cur.paid += r.paid
    bucket.set(key, cur)
  }
  return [...bucket.values()].map((r) => {
    const unpaid = r.payable - r.paid
    const payRatio = r.payable > 0 ? r.paid / r.payable : null
    return { ...r, unpaid, payRatio }
  }).sort((a, b) => b.unpaid - a.unpaid)
}

function aggregateByContract(rows: PivotRow[]) {
  const bucket = new Map<string, PivotRow>()
  for (const r of rows) {
    const key = `${r.contractNo}|${r.salesperson}|${r.department}|${r.company}`
    const cur = bucket.get(key) || {
      key,
      contractNo: r.contractNo,
      salesperson: r.salesperson,
      department: r.department,
      company: r.company,
      payable: 0,
      paid: 0,
      unpaid: 0,
      payRatio: null,
    }
    cur.payable += r.payable
    cur.paid += r.paid
    bucket.set(key, cur)
  }
  return [...bucket.values()].map((r) => {
    const unpaid = r.payable - r.paid
    const payRatio = r.payable > 0 ? r.paid / r.payable : null
    return { ...r, unpaid, payRatio }
  }).sort((a, b) => a.contractNo.localeCompare(b.contractNo))
}

function sumPivot(rows: PivotRow[], field: keyof Pick<PivotRow, 'payable' | 'paid' | 'unpaid'>) {
  return rows.reduce((s, r) => s + r[field], 0)
}

function BizBonusPaymentDashboard({ mode }: { mode: DashboardMode }) {
  const editable = mode === 'v1'
  usePageTitle(editable ? '业务奖金流转单支付情况（可修改）' : '业务奖金流转单支付情况')
  const nav = useNavigate()
  const userSelect = useUserSelect()
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [loadingInit, setLoadingInit] = useState(true)
  const [loading, setLoading] = useState(false)
  const [contractNo, setContractNo] = useState('')
  const [salespersonId, setSalespersonId] = useState<string | undefined>()
  const [departmentId, setDepartmentId] = useState<string | undefined>()
  const [companyName, setCompanyName] = useState('')
  const [bonusNo, setBonusNo] = useState('')
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(defaultYearRange())
  const [summary, setSummary] = useState({
    count: 0, sum_current_bonus: 0, sum_paid_amount: 0, sum_unpaid_amount: 0,
  })
  const [rows, setRows] = useState<FormInstance[]>([])
  const [pivotSource, setPivotSource] = useState<FormInstance[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [nameMaps, setNameMaps] = useState({
    dept: {} as Record<string, string>,
    person: {} as Record<string, string>,
  })

  const filtersJson = useMemo(
    () => JSON.stringify(buildFilters(contractNo, salespersonId, departmentId, companyName, bonusNo, dateRange)),
    [contractNo, salespersonId, departmentId, companyName, bonusNo, dateRange],
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await lowcodeApi.ensureBuiltin('commission_database')
        if (!cancelled) setTemplateId(res.data.id)
      } catch {
        if (!cancelled) message.error('加载提成数据库失败')
      } finally {
        if (!cancelled) setLoadingInit(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const load = useCallback(async () => {
    if (!templateId) return
    setLoading(true)
    try {
      const pivotPageSize = mode === 'v2' ? 5000 : 0
      const requests: Promise<unknown>[] = [
        lowcodeApi.commissionDatabaseDashboardSummary({ template_id: templateId, filters: filtersJson }),
        lowcodeApi.listInstances({
          template_id: templateId,
          pageNo,
          pageSize,
          filters: filtersJson,
        }),
      ]
      if (pivotPageSize > 0) {
        requests.push(lowcodeApi.listInstances({
          template_id: templateId,
          pageNo: 1,
          pageSize: pivotPageSize,
          filters: filtersJson,
        }))
      }
      const results = await Promise.all(requests)
      const sumRes = results[0] as Awaited<ReturnType<typeof lowcodeApi.commissionDatabaseDashboardSummary>>
      const listRes = results[1] as Awaited<ReturnType<typeof lowcodeApi.listInstances>>
      setSummary(sumRes.data)
      setRows(listRes.data.items)
      setTotal(listRes.data.total)
      if (pivotPageSize > 0 && results[2]) {
        const pivotRes = results[2] as Awaited<ReturnType<typeof lowcodeApi.listInstances>>
        setPivotSource(pivotRes.data.items)
      }

      const deptIds = new Set<string>()
      const personIds = new Set<string>()
      const scan = [...listRes.data.items, ...(results[2] ? (results[2] as Awaited<ReturnType<typeof lowcodeApi.listInstances>>).data.items : [])]
      for (const r of scan) {
        const fd = r.form_data || {}
        const dep = fd.department
        if (dep) deptIds.add(refId(dep))
        const sp = fd.salesperson
        if (sp) personIds.add(refId(sp))
      }
      const [dept, person] = await Promise.all([
        getDeptNameMap([...deptIds]),
        getPersonLabelMap([...personIds]),
      ])
      setNameMaps({ dept, person })
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '加载仪表盘失败')
    } finally {
      setLoading(false)
    }
  }, [templateId, filtersJson, pageNo, pageSize, mode])

  useEffect(() => {
    if (templateId) load()
  }, [templateId, load])

  const applyFilters = () => {
    if (pageNo !== 1) setPageNo(1)
    else load()
  }

  const pivotRows = useMemo(
    () => buildPivotRows(pivotSource.length ? pivotSource : rows, nameMaps),
    [pivotSource, rows, nameMaps],
  )
  const salespersonPivot = useMemo(() => aggregateBySalesperson(pivotRows), [pivotRows])
  const contractPivot = useMemo(() => aggregateByContract(pivotRows), [pivotRows])

  const pivotMetricCols: ColumnsType<PivotRow> = [
    { title: '应付奖金', dataIndex: 'payable', align: 'right', width: 120, render: (v) => fmtMoney(v) },
    { title: '已付金额', dataIndex: 'paid', align: 'right', width: 120, render: (v) => fmtMoney(v) },
    { title: '未付金额', dataIndex: 'unpaid', align: 'right', width: 120, render: (v) => fmtMoney(v) },
    { title: '支付比例', dataIndex: 'payRatio', align: 'right', width: 100, render: (v) => fmtPct(v) },
  ]

  const columns: ColumnsType<FormInstance> = useMemo(() => [
    {
      title: '奖金编号',
      key: 'bonus_no',
      width: 130,
      fixed: 'left',
      render: (_, r) => {
        const no = String((r.form_data || {}).bonus_no || r.business_no || r.id.slice(0, 8))
        return (
          <a className="font-mono" onClick={() => nav('/commission-database', { state: { openId: r.id } })}>
            {no}
          </a>
        )
      },
    },
    ...LIST_COLUMNS.filter((fid) => fid !== 'bonus_no').map((fid) => ({
      title: COL_LABELS[fid],
      key: fid,
      width: fid === 'company_name' ? 180 : fid === 'contract_no' ? 150 : 110,
      align: (fid === 'contract_amount' || fid === 'current_bonus' || fid === 'field_9') ? 'right' as const : undefined,
      render: (_: unknown, r: FormInstance) => cellText(fid, (r.form_data || {})[fid], nameMaps),
    })),
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s: string) => {
        const t = STATUS_TAG[s] || { color: 'default', text: s }
        return <Tag color={t.color}>{t.text}</Tag>
      },
    },
    ...(editable ? [{
      title: '操作',
      key: 'actions',
      width: 80,
      fixed: 'right' as const,
      render: (_: unknown, r: FormInstance) => (
        <Button
          type="link"
          size="small"
          icon={<EditOutlined />}
          onClick={() => nav('/commission-database', { state: { openId: r.id } })}
        >
          编辑
        </Button>
      ),
    }] : []),
  ], [editable, nameMaps, nav])

  const paymentSubCols: ColumnsType<PaymentLine> = [
    { title: '支付时间', dataIndex: 'field_5', width: 120, render: (v) => (v ? String(v).slice(0, 10) : '—') },
    { title: '金额', dataIndex: 'field_6', align: 'right', width: 100, render: (v) => fmtMoney(v) },
    { title: '形式', dataIndex: 'field_7', width: 100 },
  ]

  if (loadingInit) {
    return (
      <div className="flex justify-center items-center py-24">
        <Spin size="large" tip="正在准备业务奖金支付仪表盘…" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 min-h-0">
      <div className="flex justify-between items-center flex-wrap gap-2 shrink-0">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/commission-database')}>返回列表</Button>
          <Title level={4} style={{ margin: 0 }}>
            {editable ? '业务奖金流转单支付情况（可修改）' : '业务奖金流转单支付情况'}
          </Title>
        </Space>
        <Space>
          <Button icon={<UnorderedListOutlined />} onClick={() => nav('/commission-database')}>数据管理</Button>
          {editable && (
            <Button type="primary" icon={<EditOutlined />} onClick={() => nav('/commission-database')}>
              批量修改
            </Button>
          )}
        </Space>
      </div>

      <Card size="small" className="shrink-0" styles={{ body: { padding: '14px 16px' } }}>
        <Flex gap={16} align="flex-end" wrap="wrap">
          <div className="shrink-0" style={{ minWidth: 160, paddingRight: 8, borderRight: '1px solid #f0f0f0' }}>
            <Text type="secondary" className="text-xs">应付奖金合计</Text>
            <div style={{ fontSize: 28, fontWeight: 600, color: '#0db3a6', lineHeight: 1.2, marginTop: 4 }}>
              {fmtMoney(summary.sum_current_bonus)}
            </div>
            <Text type="secondary" className="text-xs">
              已付 {fmtMoney(summary.sum_paid_amount)} · 未付 {fmtMoney(summary.sum_unpaid_amount)}
            </Text>
            <div><Text type="secondary" className="text-xs">共 {summary.count.toLocaleString('zh-CN')} 条</Text></div>
          </div>

          <Flex gap={8} wrap="wrap" align="flex-end" style={{ flex: 1, minWidth: 360 }}>
            <Input allowClear placeholder="合同号" style={{ width: 130 }} value={contractNo}
              onChange={(e) => setContractNo(e.target.value)} onPressEnter={applyFilters} />
            <Select
              allowClear
              showSearch
              placeholder="业务员"
              style={{ width: 150 }}
              value={salespersonId}
              onChange={(v) => setSalespersonId(v)}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onOpenChange={userSelect.onDropdownVisibleChange}
              filterOption={false}
              loading={userSelect.loading}
            />
            <div style={{ width: 150 }}>
              <DepartmentSelect
                allowClear
                placeholder="部门"
                value={departmentId}
                onChange={(v) => setDepartmentId(typeof v === 'string' ? v : undefined)}
              />
            </div>
            <Input allowClear placeholder="单位名称" style={{ width: 140 }} value={companyName}
              onChange={(e) => setCompanyName(e.target.value)} onPressEnter={applyFilters} />
            <Input allowClear placeholder="奖金编号" style={{ width: 130 }} value={bonusNo}
              onChange={(e) => setBonusNo(e.target.value)} onPressEnter={applyFilters} />
            <RangePicker
              value={dateRange}
              onChange={(v) => setDateRange(v as [Dayjs, Dayjs] | null)}
              allowClear={false}
              style={{ width: 240 }}
            />
            <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={applyFilters}>
              查询
            </Button>
          </Flex>
        </Flex>
      </Card>

      <Card
        title={editable ? '支付状态（可修改）' : '支付状态（不能修改）'}
        className="flex-1 min-h-0"
        styles={{ body: { padding: '0 0 8px' } }}
      >
        <Table<FormInstance>
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={rows}
          scroll={{ x: 1400, y: mode === 'v2' ? 360 : 'calc(100vh - 380px)' }}
          expandable={{
            expandedRowRender: (r) => {
              const lines = ((r.form_data || {}).payment_status || []) as PaymentLine[]
              if (!lines.length) return <Text type="secondary">暂无支付记录</Text>
              return (
                <Table<PaymentLine>
                  rowKey={(_, i) => String(i)}
                  size="small"
                  pagination={false}
                  columns={paymentSubCols}
                  dataSource={lines}
                />
              )
            },
            rowExpandable: (r) => {
              const lines = (r.form_data || {}).payment_status
              return Array.isArray(lines) && lines.length > 0
            },
          }}
          pagination={{
            current: pageNo,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ['20', '50', '100'],
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPageNo(p); if (ps !== pageSize) setPageSize(ps) },
          }}
        />
      </Card>

      {mode === 'v2' && (
        <>
          <Card title="业务员未付奖金表" size="small">
            <Table<PivotRow>
              rowKey="key"
              size="small"
              loading={loading}
              scroll={{ x: 1100 }}
              dataSource={salespersonPivot}
              pagination={{ pageSize: 50, showSizeChanger: true }}
              columns={[
                { title: '业务员', dataIndex: 'salesperson', width: 100 },
                { title: '部门', dataIndex: 'department', width: 120 },
                { title: '单位名称', dataIndex: 'company', width: 180 },
                { title: '合同号', dataIndex: 'contractNo', width: 150 },
                ...pivotMetricCols,
              ]}
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} colSpan={4}><Text strong>合计</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right"><Text strong>{fmtMoney(sumPivot(salespersonPivot, 'payable'))}</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right"><Text strong>{fmtMoney(sumPivot(salespersonPivot, 'paid'))}</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={6} align="right"><Text strong>{fmtMoney(sumPivot(salespersonPivot, 'unpaid'))}</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={7} />
                </Table.Summary.Row>
              )}
            />
          </Card>

          <Card title="合同号奖金支付情况" size="small">
            <Table<PivotRow>
              rowKey="key"
              size="small"
              loading={loading}
              scroll={{ x: 1100 }}
              dataSource={contractPivot}
              pagination={{ pageSize: 50, showSizeChanger: true }}
              columns={[
                { title: '合同号', dataIndex: 'contractNo', width: 150 },
                { title: '业务员', dataIndex: 'salesperson', width: 100 },
                { title: '部门', dataIndex: 'department', width: 120 },
                { title: '单位名称', dataIndex: 'company', width: 180 },
                ...pivotMetricCols.slice(0, 3),
              ]}
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} colSpan={4}><Text strong>合计</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right"><Text strong>{fmtMoney(sumPivot(contractPivot, 'payable'))}</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right"><Text strong>{fmtMoney(sumPivot(contractPivot, 'paid'))}</Text></Table.Summary.Cell>
                  <Table.Summary.Cell index={6} align="right"><Text strong>{fmtMoney(sumPivot(contractPivot, 'unpaid'))}</Text></Table.Summary.Cell>
                </Table.Summary.Row>
              )}
            />
          </Card>
        </>
      )}
    </div>
  )
}

export function BizBonusPaymentDashboardV1() {
  return <BizBonusPaymentDashboard mode="v1" />
}

export function BizBonusPaymentDashboardV2() {
  return <BizBonusPaymentDashboard mode="v2" />
}

export default BizBonusPaymentDashboardV1
