/**
 * 发货借据仪表盘 — 对齐简道云数据中心「借据 / 发货借据」：
 * 筛选 + 借据总金额汇总；下方「发货借据逾期情况明细」列表。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Card, Flex, Input, Space, Table, Tag, Typography, Spin, message,
} from 'antd'
import {
  ArrowLeftOutlined, ReloadOutlined, UnorderedListOutlined, PlusOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { lowcodeApi } from '@/api/lowcode'
import type { FormInstance } from '@/types/lowcode'
import DepartmentSelect from '@/components/DepartmentSelect'
import PersonField from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getCustomerLabelMap } from '@/components/lowcode/fields/CustomerField'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getContractLabelMap } from '@/components/lowcode/fields/ContractField'
import type { FormFilterDsl } from '@/components/lowcode/formInstanceFilterUtils'
import { usePageTitle } from '@/hooks/usePageTitle'
import { recordListNo } from '@/utils/formInstanceListNo'

const { Title, Text } = Typography

/** 简道云「逾期天数（减了7天）」：到期日 = 发货借据时间 + 7 天 */
const GRACE_DAYS = 7

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  submitted: { color: 'blue', text: '已提交' },
  running: { color: 'gold', text: '审批中' },
  completed: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
  withdrawn: { color: 'default', text: '已撤回' },
}

const COL_LABELS: Record<string, string> = {
  field: '借据日期',
  field_6: '业务部门',
  sales_person: '业务员',
  customer_name: '客户名称',
  contract_no: '图纸编号',
  field_13: '借据总金额',
  field_19: '发货借据时间',
  due_date: '到期日',
  overdue_days: '逾期天数',
  overdue_interest: 'n逾期利息',
  field_16: '预计回款时间',
}

function fmtMoney(v: unknown) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0.00'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function refId(val: unknown): string {
  if (val == null || val === '') return ''
  if (typeof val === 'object' && val && 'id' in val) return String((val as { id: string }).id)
  return String(val)
}

function fmtDate(v: unknown) {
  if (v == null || v === '') return '—'
  const d = dayjs(String(v))
  return d.isValid() ? d.format('YYYY-MM-DD') : String(v)
}

function buildFilters(
  customer: string,
  departmentId: string | undefined,
  salesPersonId: string | undefined,
  drawingNo: string,
): FormFilterDsl {
  const rules: FormFilterDsl['rules'] = [
    { field: 'field_3', op: 'eq', value: '发货借据' },
  ]
  const c = customer.trim()
  if (c) rules.push({ field: 'customer_name', op: 'contains', value: c })
  if (departmentId) rules.push({ field: 'field_6', op: 'eq', value: departmentId })
  if (salesPersonId) rules.push({ field: 'sales_person', op: 'eq', value: salesPersonId })
  const d = drawingNo.trim()
  if (d) rules.push({ field: 'contract_no', op: 'contains', value: d })
  return { match: 'all', rules }
}

function computeRowMetrics(fd: Record<string, unknown>) {
  const shipmentAt = fd.field_19 ? dayjs(String(fd.field_19)) : null
  const paidAt = fd.field_18 ? dayjs(String(fd.field_18)) : null
  const dueDate = shipmentAt?.isValid() ? shipmentAt.add(GRACE_DAYS, 'day') : null
  let overdueDays = 0
  if (dueDate?.isValid() && !(paidAt?.isValid())) {
    overdueDays = Math.max(0, dayjs().startOf('day').diff(dueDate.startOf('day'), 'day'))
  }
  const amount = Number(fd.field_13)
  const storedInterest = Number(fd.field_14)
  const overdueInterest = Number.isFinite(storedInterest) && storedInterest > 0
    ? storedInterest
    : (overdueDays > 0 && Number.isFinite(amount) ? amount * overdueDays * 0.0003 : 0)
  return { dueDate, overdueDays, overdueInterest }
}

export default function ShipmentLoanDashboard() {
  usePageTitle('发货借据')
  const nav = useNavigate()
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [loadingInit, setLoadingInit] = useState(true)
  const [loading, setLoading] = useState(false)
  const [customer, setCustomer] = useState('')
  const [departmentId, setDepartmentId] = useState<string | undefined>()
  const [salesPersonId, setSalesPersonId] = useState<string | undefined>()
  const [drawingNo, setDrawingNo] = useState('')
  const [summary, setSummary] = useState({ count: 0, sum: 0 })
  const [rows, setRows] = useState<FormInstance[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [nameMaps, setNameMaps] = useState({
    dept: {} as Record<string, string>,
    customer: {} as Record<string, string>,
    person: {} as Record<string, string>,
    contract: {} as Record<string, string>,
  })

  const filtersJson = useMemo(
    () => JSON.stringify(buildFilters(customer, departmentId, salesPersonId, drawingNo)),
    [customer, departmentId, salesPersonId, drawingNo],
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await lowcodeApi.ensureBuiltin('contract_shipment_loan')
        if (!cancelled) setTemplateId(res.data.id)
      } catch {
        if (!cancelled) message.error('加载合同及发货借据流程失败')
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
      const [sumRes, listRes] = await Promise.all([
        lowcodeApi.contractShipmentLoanDashboardSummary({
          template_id: templateId,
          filters: filtersJson,
        }),
        lowcodeApi.listInstances({
          template_id: templateId,
          pageNo,
          pageSize,
          filters: filtersJson,
        }),
      ])
      setSummary(sumRes.data)
      setRows(listRes.data.items)
      setTotal(listRes.data.total)

      const deptIds = new Set<string>()
      const custIds = new Set<string>()
      const personIds = new Set<string>()
      const contractIds = new Set<string>()
      for (const r of listRes.data.items) {
        const fd = r.form_data || {}
        const dep = fd.field_6
        if (dep) deptIds.add(refId(dep))
        const cu = fd.customer_name
        if (cu) custIds.add(refId(cu))
        const sp = fd.sales_person
        if (sp) personIds.add(refId(sp))
        const cn = fd.contract_no
        if (cn) contractIds.add(refId(cn))
      }
      const [dept, customerMap, person, contract] = await Promise.all([
        getDeptNameMap([...deptIds]),
        getCustomerLabelMap([...custIds]),
        getPersonLabelMap([...personIds]),
        getContractLabelMap([...contractIds]),
      ])
      setNameMaps({ dept, customer: customerMap, person, contract })
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '加载发货借据仪表盘失败')
    } finally {
      setLoading(false)
    }
  }, [templateId, filtersJson, pageNo, pageSize])

  useEffect(() => {
    if (templateId) load()
  }, [templateId, load])

  const applyFilters = () => {
    if (pageNo !== 1) setPageNo(1)
    else load()
  }

  const columns: ColumnsType<FormInstance> = useMemo(() => [
    {
      title: '流水号',
      key: 'list_no',
      width: 130,
      fixed: 'left',
      render: (_, r) => {
        const no = recordListNo(r, [])
        return (
          <a className="font-mono" onClick={() => nav('/contract-shipment-loans', { state: { openId: r.id } })}>
            {no}
          </a>
        )
      },
    },
    {
      title: COL_LABELS.field,
      key: 'field',
      width: 110,
      render: (_, r) => fmtDate((r.form_data || {}).field),
    },
    {
      title: COL_LABELS.field_6,
      key: 'field_6',
      width: 120,
      render: (_, r) => nameMaps.dept[refId((r.form_data || {}).field_6)] || '—',
    },
    {
      title: COL_LABELS.sales_person,
      key: 'sales_person',
      width: 90,
      render: (_, r) => nameMaps.person[refId((r.form_data || {}).sales_person)] || '—',
    },
    {
      title: COL_LABELS.customer_name,
      key: 'customer_name',
      width: 160,
      render: (_, r) => nameMaps.customer[refId((r.form_data || {}).customer_name)] || '—',
    },
    {
      title: COL_LABELS.contract_no,
      key: 'contract_no',
      width: 130,
      render: (_, r) => nameMaps.contract[refId((r.form_data || {}).contract_no)] || '—',
    },
    {
      title: COL_LABELS.field_13,
      key: 'field_13',
      width: 120,
      align: 'right',
      render: (_, r) => fmtMoney((r.form_data || {}).field_13),
    },
    {
      title: COL_LABELS.field_19,
      key: 'field_19',
      width: 120,
      render: (_, r) => fmtDate((r.form_data || {}).field_19),
    },
    {
      title: COL_LABELS.due_date,
      key: 'due_date',
      width: 110,
      render: (_, r) => {
        const { dueDate } = computeRowMetrics(r.form_data || {})
        return dueDate?.isValid() ? dueDate.format('YYYY-MM-DD') : '—'
      },
    },
    {
      title: COL_LABELS.overdue_days,
      key: 'overdue_days',
      width: 90,
      align: 'right',
      render: (_, r) => {
        const { overdueDays } = computeRowMetrics(r.form_data || {})
        return overdueDays > 0 ? <Text type="danger">{overdueDays}</Text> : overdueDays
      },
    },
    {
      title: COL_LABELS.overdue_interest,
      key: 'overdue_interest',
      width: 110,
      align: 'right',
      render: (_, r) => fmtMoney(computeRowMetrics(r.form_data || {}).overdueInterest),
    },
    {
      title: COL_LABELS.field_16,
      key: 'field_16',
      width: 120,
      render: (_, r) => fmtDate((r.form_data || {}).field_16),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s: string) => {
        const t = STATUS_TAG[s] || { color: 'default', text: s }
        return <Tag color={t.color}>{t.text}</Tag>
      },
    },
  ], [nameMaps, nav])

  if (loadingInit) {
    return (
      <div className="flex justify-center items-center py-24">
        <Spin size="large" tip="正在准备发货借据仪表盘…" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 min-h-0">
      <div className="flex justify-between items-center flex-wrap gap-2 shrink-0">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/contract-shipment-loans')}>返回列表</Button>
          <Title level={4} style={{ margin: 0 }}>发货借据</Title>
        </Space>
        <Space>
          <Button icon={<UnorderedListOutlined />} onClick={() => nav('/contract-shipment-loans')}>数据管理</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => nav('/contract-shipment-loans/fill')}>新增</Button>
        </Space>
      </div>

      <Card size="small" className="shrink-0" styles={{ body: { padding: '14px 16px' } }}>
        <Flex gap={16} align="flex-end" wrap="wrap">
          <div className="shrink-0" style={{ minWidth: 148, paddingRight: 8, borderRight: '1px solid #f0f0f0' }}>
            <Text type="secondary" className="text-xs">借据总金额</Text>
            <div style={{ fontSize: 30, fontWeight: 600, color: '#0db3a6', lineHeight: 1.2, marginTop: 4 }}>
              {fmtMoney(summary.sum)}
            </div>
            <Text type="secondary" className="text-xs">共 {summary.count.toLocaleString('zh-CN')} 条发货借据</Text>
          </div>

          <Flex gap={8} wrap="wrap" align="flex-end" style={{ flex: 1, minWidth: 360 }}>
            <div style={{ width: 160 }}>
              <DepartmentSelect
                allowClear
                placeholder="业务部门"
                value={departmentId}
                onChange={(v) => setDepartmentId(typeof v === 'string' ? v : undefined)}
              />
            </div>
            <div style={{ width: 140 }}>
              <PersonField
                placeholder="业务员"
                value={salesPersonId}
                onChange={(v) => setSalesPersonId(typeof v === 'string' ? v : undefined)}
              />
            </div>
            <Input
              allowClear
              placeholder="客户名称"
              style={{ width: 140 }}
              value={customer}
              onChange={(e) => setCustomer(e.target.value)}
              onPressEnter={applyFilters}
            />
            <Input
              allowClear
              placeholder="图纸编号"
              style={{ width: 130 }}
              value={drawingNo}
              onChange={(e) => setDrawingNo(e.target.value)}
              onPressEnter={applyFilters}
            />
            <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={applyFilters}>
              查询
            </Button>
          </Flex>
        </Flex>
      </Card>

      <Card
        title="发货借据逾期情况明细"
        className="flex-1 min-h-0"
        styles={{ body: { padding: '0 0 8px' } }}
      >
        <Table<FormInstance>
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={rows}
          scroll={{ x: 1400, y: 'calc(100vh - 320px)' }}
          pagination={{
            current: pageNo,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ['20', '50', '100'],
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => {
              setPageNo(p)
              setPageSize(ps)
            },
          }}
        />
      </Card>
    </div>
  )
}
