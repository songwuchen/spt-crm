/**
 * 收款登记仪表盘 — 对齐简道云「合同管理 / 收款登记仪表盘」：
 * 首行：来款合计 + 筛选；下方全宽数据列表。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Card, DatePicker, Flex, Input, Space, Table, Tag, Typography, Spin, message,
} from 'antd'
import {
  ArrowLeftOutlined, ReloadOutlined, UnorderedListOutlined, PlusOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { lowcodeApi } from '@/api/lowcode'
import type { FormInstance } from '@/types/lowcode'
import DepartmentSelect from '@/components/DepartmentSelect'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getCustomerLabelMap } from '@/components/lowcode/fields/CustomerField'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import type { FormFilterDsl } from '@/components/lowcode/formInstanceFilterUtils'
import { usePageTitle } from '@/hooks/usePageTitle'
import { recordListNo } from '@/utils/formInstanceListNo'

const { Title, Text } = Typography
const { RangePicker } = DatePicker

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  submitted: { color: 'blue', text: '已提交' },
  running: { color: 'gold', text: '审批中' },
  completed: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
  withdrawn: { color: 'default', text: '已撤回' },
}

const LIST_COLUMNS = [
  'payment_date', 'customer_name', 'department',
  'payment_total', 'sales_person',
] as const

const COL_LABELS: Record<string, string> = {
  payment_date: '来款日期',
  customer_name: '单位名称',
  department: '部门',
  payment_total: '来款合计',
  sales_person: '业务人员',
}

function defaultYearRange(): [Dayjs, Dayjs] {
  return [dayjs().startOf('year'), dayjs().endOf('year')]
}

function buildFilters(
  customer: string,
  departmentId: string | undefined,
  drawingNo: string,
  dateRange: [Dayjs, Dayjs] | null,
): FormFilterDsl {
  const rules: FormFilterDsl['rules'] = []
  const c = customer.trim()
  if (c) rules.push({ field: 'customer_name', op: 'contains', value: c })
  if (departmentId) rules.push({ field: 'department', op: 'eq', value: departmentId })
  const d = drawingNo.trim()
  if (d) rules.push({ field: 'drawing_no', op: 'eq', value: d })
  const dr = dateRange || defaultYearRange()
  rules.push({
    field: 'payment_date',
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

function cellText(field: string, val: unknown, maps: {
  dept: Record<string, string>
  customer: Record<string, string>
  person: Record<string, string>
}) {
  if (val == null || val === '') return '—'
  if (field === 'department') {
    const id = typeof val === 'object' && val && 'id' in val ? String((val as { id: string }).id) : String(val)
    return maps.dept[id] || id
  }
  if (field === 'customer_name') {
    const id = typeof val === 'object' && val && 'id' in val ? String((val as { id: string }).id) : String(val)
    return maps.customer[id] || (typeof val === 'object' && val && 'name' in val ? String((val as { name: string }).name) : String(val))
  }
  if (field === 'sales_person') {
    const id = typeof val === 'object' && val && 'id' in val ? String((val as { id: string }).id) : String(val)
    return maps.person[id] || id
  }
  if (field === 'payment_total') return fmtMoney(val)
  return String(val)
}

export default function PaymentRegistrationDashboard() {
  usePageTitle('收款登记仪表盘')
  const nav = useNavigate()
  const [templateId, setTemplateId] = useState<string | null>(null)
  const [loadingInit, setLoadingInit] = useState(true)
  const [loading, setLoading] = useState(false)
  const [customer, setCustomer] = useState('')
  const [departmentId, setDepartmentId] = useState<string | undefined>()
  const [drawingNo, setDrawingNo] = useState('')
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(defaultYearRange())
  const [summary, setSummary] = useState({ count: 0, sum: 0 })
  const [rows, setRows] = useState<FormInstance[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [nameMaps, setNameMaps] = useState({
    dept: {} as Record<string, string>,
    customer: {} as Record<string, string>,
    person: {} as Record<string, string>,
  })

  const filtersJson = useMemo(
    () => JSON.stringify(buildFilters(customer, departmentId, drawingNo, dateRange)),
    [customer, departmentId, drawingNo, dateRange],
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await lowcodeApi.ensureBuiltin('payment_registration')
        if (!cancelled) setTemplateId(res.data.id)
      } catch {
        if (!cancelled) message.error('加载收款登记表单失败')
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
        lowcodeApi.paymentRegistrationDashboardSummary({
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
      for (const r of listRes.data.items) {
        const fd = r.form_data || {}
        const dep = fd.department
        if (dep) deptIds.add(typeof dep === 'object' ? String((dep as { id: string }).id) : String(dep))
        const cu = fd.customer_name
        if (cu) custIds.add(typeof cu === 'object' ? String((cu as { id: string }).id) : String(cu))
        const sp = fd.sales_person
        if (sp) personIds.add(typeof sp === 'object' ? String((sp as { id: string }).id) : String(sp))
      }
      const [dept, customerMap, person] = await Promise.all([
        getDeptNameMap([...deptIds]),
        getCustomerLabelMap([...custIds]),
        getPersonLabelMap([...personIds]),
      ])
      setNameMaps({ dept, customer: customerMap, person })
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '加载仪表盘失败')
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
          <a className="font-mono" onClick={() => nav('/payment-registrations', { state: { openId: r.id } })}>
            {no}
          </a>
        )
      },
    },
    ...LIST_COLUMNS.map((fid) => ({
      title: COL_LABELS[fid],
      key: fid,
      width: fid === 'payment_total' ? 120 : fid === 'customer_name' ? 180 : 110,
      align: fid === 'payment_total' ? 'right' as const : undefined,
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
  ], [nameMaps, nav])

  if (loadingInit) {
    return (
      <div className="flex justify-center items-center py-24">
        <Spin size="large" tip="正在准备收款登记仪表盘…" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 min-h-0">
      <div className="flex justify-between items-center flex-wrap gap-2 shrink-0">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/payment-registrations')}>返回列表</Button>
          <Title level={4} style={{ margin: 0 }}>收款登记仪表盘</Title>
        </Space>
        <Space>
          <Button icon={<UnorderedListOutlined />} onClick={() => nav('/payment-registrations')}>数据管理</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => nav('/payment-registrations/fill')}>新增</Button>
        </Space>
      </div>

      {/* 简道云同款：指标 + 筛选同一行 */}
      <Card size="small" className="shrink-0" styles={{ body: { padding: '14px 16px' } }}>
        <Flex gap={16} align="flex-end" wrap="wrap">
          <div className="shrink-0" style={{ minWidth: 148, paddingRight: 8, borderRight: '1px solid #f0f0f0' }}>
            <Text type="secondary" className="text-xs">来款合计</Text>
            <div style={{ fontSize: 30, fontWeight: 600, color: '#0db3a6', lineHeight: 1.2, marginTop: 4 }}>
              {fmtMoney(summary.sum)}
            </div>
            <Text type="secondary" className="text-xs">共 {summary.count.toLocaleString('zh-CN')} 条</Text>
          </div>

          <Flex gap={8} wrap="wrap" align="flex-end" style={{ flex: 1, minWidth: 320 }}>
            <Input
              allowClear
              placeholder="单位名称"
              style={{ width: 150 }}
              value={customer}
              onChange={(e) => setCustomer(e.target.value)}
              onPressEnter={applyFilters}
            />
            <div style={{ width: 160 }}>
              <DepartmentSelect
                allowClear
                placeholder="部门"
                value={departmentId}
                onChange={(v) => setDepartmentId(typeof v === 'string' ? v : undefined)}
              />
            </div>
            <Input
              allowClear
              placeholder="图纸编号"
              style={{ width: 140 }}
              value={drawingNo}
              onChange={(e) => setDrawingNo(e.target.value)}
              onPressEnter={applyFilters}
            />
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
        title="收款登记"
        className="flex-1 min-h-0"
        styles={{ body: { padding: '0 0 8px' } }}
      >
        <Table<FormInstance>
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={rows}
          scroll={{ x: 980, y: 'calc(100vh - 320px)' }}
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
