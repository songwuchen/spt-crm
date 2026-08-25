/**
 * 合同管理仪表盘 — 对齐简道云「数据中心 / 合同管理 / 合同管理仪表盘」：
 * 全局筛选 + 年度/当天指标 + 部门/月度/业务人员/客户等图表。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Card, Col, DatePicker, Flex, Input, Row, Space, Spin, Statistic, Table, Typography, message,
} from 'antd'
import {
  ArrowLeftOutlined, ReloadOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import { Area, Column, Pie } from '@ant-design/charts'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { contractApi } from '@/api/contract'
import CustomerProvinceMap from '@/components/contract/CustomerProvinceMap'
import DepartmentSelect from '@/components/DepartmentSelect'
import PersonField from '@/components/lowcode/fields/PersonField'
import { usePageTitle } from '@/hooks/usePageTitle'

const { Title, Text } = Typography
const { RangePicker } = DatePicker

export interface DashboardBucket {
  label: string
  count: number
  amount: number
}

export interface DeptWorkloadRow {
  month: string
  department: string
  workload: string
  count: number
  amount: number
}

export interface CustomerDashboardStats {
  total_count: number
  founded_over_10y_count: number
  by_industry: DashboardBucket[]
  by_nature: DashboardBucket[]
  by_province: DashboardBucket[]
  map_by_province: DashboardBucket[]
}

export interface ContractDashboardSummary {
  count: number
  amount_total: number
  year_amount: number
  today_amount: number
  card_date_from?: string | null
  card_date_to?: string | null
  by_year: DashboardBucket[]
  by_month: DashboardBucket[]
  by_department: DashboardBucket[]
  by_sales: DashboardBucket[]
  top_customers: DashboardBucket[]
  by_industry_contract: DashboardBucket[]
  dept_workload: DeptWorkloadRow[]
  customers: CustomerDashboardStats | null
}

function defaultYearRange(): [Dayjs, Dayjs] {
  return [dayjs().startOf('year'), dayjs().endOf('year')]
}

function fmtMoney(v: unknown) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0.00'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function MetricCard({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <Card size="small" styles={{ body: { padding: '14px 16px' } }}>
      <Text type="secondary" className="text-xs">{title}</Text>
      <div style={{ fontSize: 28, fontWeight: 600, color: '#0db3a6', lineHeight: 1.2, marginTop: 4 }}>
        {value}
      </div>
      {sub ? <Text type="secondary" className="text-xs">{sub}</Text> : null}
    </Card>
  )
}

export default function ContractManagementDashboard() {
  usePageTitle('合同管理仪表盘')
  const nav = useNavigate()
  const [loading, setLoading] = useState(false)
  const [customer, setCustomer] = useState('')
  const [departmentId, setDepartmentId] = useState<string | undefined>()
  const [assigneeId, setAssigneeId] = useState<string | undefined>()
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(defaultYearRange())
  const [data, setData] = useState<ContractDashboardSummary | null>(null)

  const queryParams = useMemo(() => {
    const dr = dateRange || defaultYearRange()
    return {
      customer_name: customer.trim() || undefined,
      department_id: departmentId,
      assignee_id: assigneeId,
      card_date_from: dr[0].format('YYYY-MM-DD'),
      card_date_to: dr[1].format('YYYY-MM-DD'),
    }
  }, [customer, departmentId, assigneeId, dateRange])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await contractApi.dashboardSummary(queryParams) as { data: ContractDashboardSummary }
      setData(res.data)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '加载仪表盘失败')
    } finally {
      setLoading(false)
    }
  }, [queryParams])

  useEffect(() => { load() }, [load])

  const applyFilters = () => load()

  const monthChart = useMemo(
    () => (data?.by_month || []).map((d) => ({ month: d.label, amount: d.amount })),
    [data],
  )
  const deptChart = useMemo(
    () => (data?.by_department || []).map((d) => ({ dept: d.label, amount: d.amount })),
    [data],
  )
  const deptDual = useMemo(
    () => (data?.by_department || []).flatMap((d) => ([
      { dept: d.label, type: '合同数量', value: d.count },
      { dept: d.label, type: '合同金额', value: d.amount },
    ])),
    [data],
  )
  const deptPie = useMemo(
    () => (data?.by_department || []).slice(0, 5).map((d) => ({ type: d.label, value: d.amount })),
    [data],
  )
  const industryContractPie = useMemo(
    () => (data?.by_industry_contract || []).map((d) => ({ type: d.label, value: d.amount })),
    [data],
  )
  const custIndustryPie = useMemo(
    () => (data?.customers?.by_industry || []).map((d) => ({ type: d.label, value: d.count })),
    [data],
  )
  const custNaturePie = useMemo(
    () => (data?.customers?.by_nature || []).map((d) => ({ type: d.label, value: d.count })),
    [data],
  )

  const workloadColumns: ColumnsType<DeptWorkloadRow> = [
    { title: '下卡月份', dataIndex: 'month', width: 100 },
    { title: '部门', dataIndex: 'department', width: 120, ellipsis: true },
    { title: '工作量', dataIndex: 'workload', width: 90 },
    { title: '合同数', dataIndex: 'count', width: 72, align: 'right' },
    {
      title: '合同金额', dataIndex: 'amount', width: 120, align: 'right',
      render: (v: number) => fmtMoney(v),
    },
  ]
  const provinceColumns: ColumnsType<DashboardBucket> = [
    { title: '省份', dataIndex: 'label', ellipsis: true },
    { title: '客户数', dataIndex: 'count', width: 90, align: 'right' },
  ]

  const salesColumns: ColumnsType<{ label: string; count: number; amount: number }> = [
    { title: '业务人员', dataIndex: 'label', ellipsis: true },
    { title: '合同数', dataIndex: 'count', width: 80, align: 'right' },
    {
      title: '合同金额', dataIndex: 'amount', width: 120, align: 'right',
      render: (v: number) => fmtMoney(v),
    },
  ]
  const custColumns: ColumnsType<{ label: string; count: number; amount: number }> = [
    { title: '客户名称', dataIndex: 'label', ellipsis: true },
    { title: '合同数', dataIndex: 'count', width: 80, align: 'right' },
    {
      title: '合同金额', dataIndex: 'amount', width: 120, align: 'right',
      render: (v: number) => fmtMoney(v),
    },
  ]

  return (
    <div className="flex flex-col gap-3 min-h-0">
      <div className="flex justify-between items-center flex-wrap gap-2 shrink-0">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/contracts')}>返回列表</Button>
          <Title level={4} style={{ margin: 0 }}>合同管理仪表盘</Title>
        </Space>
        <Space>
          <Button icon={<UnorderedListOutlined />} onClick={() => nav('/contracts')}>数据管理</Button>
        </Space>
      </div>

      <Card size="small" className="shrink-0" styles={{ body: { padding: '14px 16px' } }}>
        <Flex gap={8} wrap="wrap" align="flex-end">
          <Input
            allowClear
            placeholder="客户名称"
            style={{ width: 150 }}
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            onPressEnter={applyFilters}
          />
          <RangePicker
            value={dateRange}
            onChange={(v) => setDateRange(v as [Dayjs, Dayjs] | null)}
            allowClear={false}
            style={{ width: 260 }}
            placeholder={['下卡日期起', '下卡日期止']}
          />
          <div style={{ width: 160 }}>
            <DepartmentSelect
              allowClear
              placeholder="部门"
              value={departmentId}
              onChange={(v) => setDepartmentId(typeof v === 'string' ? v : undefined)}
            />
          </div>
          <div style={{ width: 160 }}>
            <PersonField
              placeholder="业务人员"
              value={assigneeId}
              onChange={(v) => setAssigneeId(typeof v === 'string' ? v : undefined)}
            />
          </div>
          <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={applyFilters}>
            查询
          </Button>
        </Flex>
      </Card>

      {loading && !data ? (
        <div className="flex justify-center py-16"><Spin size="large" tip="正在加载…" /></div>
      ) : (
        <>
          <Row gutter={[12, 12]}>
            <Col xs={24} sm={12} md={8}>
              <MetricCard
                title="年度合同额"
                value={fmtMoney(data?.year_amount)}
                sub={`共 ${(data?.count ?? 0).toLocaleString('zh-CN')} 份合同`}
              />
            </Col>
            <Col xs={24} sm={12} md={8}>
              <MetricCard title="当天合同额" value={fmtMoney(data?.today_amount)} sub="按今日下卡日期" />
            </Col>
            <Col xs={24} md={8}>
              <Card size="small" styles={{ body: { padding: '12px 16px' } }}>
                <Statistic
                  title="筛选区间合计"
                  value={data?.amount_total ?? 0}
                  precision={2}
                  suffix="元"
                  valueStyle={{ color: '#1677ff', fontSize: 22 }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="每月合同额" size="small" loading={loading}>
            {monthChart.length ? (
              <Area
                data={monthChart}
                xField="month"
                yField="amount"
                height={260}
                style={{ fill: 'linear-gradient(-90deg, white 0%, #76DA91 100%)' }}
                axis={{ y: { title: '合同金额（元）' } }}
              />
            ) : (
              <div className="text-center text-slate-400 py-12">暂无数据</div>
            )}
          </Card>

          <Row gutter={[12, 12]}>
            <Col xs={24} lg={10}>
              <Card title="部门合同占比" size="small" loading={loading}>
                {deptPie.length ? (
                  <Pie
                    data={deptPie}
                    angleField="value"
                    colorField="type"
                    radius={0.85}
                    innerRadius={0.5}
                    height={280}
                    label={{ text: 'type', position: 'outside' }}
                    legend={{ position: 'bottom' }}
                  />
                ) : (
                  <div className="text-center text-slate-400 py-12">暂无数据</div>
                )}
              </Card>
            </Col>
            <Col xs={24} lg={14}>
              <Card title="合同数量和金额" size="small" loading={loading}>
                {deptDual.length ? (
                  <Column
                    data={deptDual}
                    xField="dept"
                    yField="value"
                    colorField="type"
                    group
                    height={280}
                    axis={{ x: { label: { autoRotate: true } } }}
                    scale={{ color: { range: ['#EFA666', '#5B8FF9'] } }}
                  />
                ) : (
                  <div className="text-center text-slate-400 py-12">暂无数据</div>
                )}
              </Card>
            </Col>
          </Row>

          <Row gutter={[12, 12]}>
            <Col xs={24} lg={14}>
              <Card title="部门排序" size="small" loading={loading}>
                {deptChart.length ? (
                  <Column
                    data={deptChart}
                    xField="dept"
                    yField="amount"
                    height={320}
                    label={{ text: 'amount', formatter: (v: string) => fmtMoney(v) }}
                    axis={{ x: { label: { autoRotate: true } }, y: { title: '合同金额（元）' } }}
                  />
                ) : (
                  <div className="text-center text-slate-400 py-12">暂无数据</div>
                )}
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card title="业务人员年度合同排序" size="small" loading={loading}>
                <Table
                  rowKey="label"
                  size="small"
                  pagination={false}
                  columns={salesColumns}
                  dataSource={data?.by_sales || []}
                  scroll={{ y: 280 }}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={[12, 12]}>
            <Col xs={24} lg={12}>
              <Card title="部门工作量统计" size="small" loading={loading}>
                <Table
                  rowKey={(r) => `${r.month}-${r.department}-${r.workload}`}
                  size="small"
                  pagination={{ pageSize: 10, showSizeChanger: false }}
                  columns={workloadColumns}
                  dataSource={data?.dept_workload || []}
                  scroll={{ x: 520, y: 280 }}
                />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="前10大客户" size="small" loading={loading}>
                <Table
                  rowKey="label"
                  size="small"
                  pagination={false}
                  columns={custColumns}
                  dataSource={data?.top_customers || []}
                />
              </Card>
            </Col>
          </Row>

          <Card title="行业合同额" size="small" loading={loading}>
            {industryContractPie.length ? (
              <Pie
                data={industryContractPie}
                angleField="value"
                colorField="type"
                radius={0.85}
                height={300}
                label={{ text: (d: { type: string; value: number }) => `${d.type}` }}
                legend={{ position: 'right' }}
              />
            ) : (
              <div className="text-center text-slate-400 py-12">暂无数据</div>
            )}
          </Card>

          {data?.customers ? (
            <>
              <Title level={5} style={{ margin: '8px 0 0' }}>客户主数据（公司客户）</Title>
              <Row gutter={[12, 12]}>
                <Col xs={24} sm={12} md={6}>
                  <MetricCard
                    title="客户数量"
                    value={String(data.customers.total_count)}
                    sub="是否公司客户=是"
                  />
                </Col>
                <Col xs={24} sm={12} md={6}>
                  <MetricCard
                    title="成立十年以上的客户"
                    value={String(data.customers.founded_over_10y_count)}
                    sub={`成立年份 ≤ ${dayjs().year() - 10}`}
                  />
                </Col>
                <Col xs={24} md={12}>
                  <Card title="省市分布" size="small">
                    <Table
                      rowKey="label"
                      size="small"
                      pagination={{ pageSize: 8, showSizeChanger: false }}
                      columns={provinceColumns}
                      dataSource={data.customers.by_province}
                      scroll={{ y: 200 }}
                    />
                  </Card>
                </Col>
              </Row>

              <Row gutter={[12, 12]}>
                <Col xs={24} lg={12}>
                  <Card title="所属行业" size="small">
                    {custIndustryPie.length ? (
                      <Pie
                        data={custIndustryPie}
                        angleField="value"
                        colorField="type"
                        radius={0.85}
                        height={280}
                        legend={{ position: 'bottom' }}
                      />
                    ) : (
                      <div className="text-center text-slate-400 py-12">暂无数据</div>
                    )}
                  </Card>
                </Col>
                <Col xs={24} lg={12}>
                  <Card title="客户性质" size="small">
                    {custNaturePie.length ? (
                      <Pie
                        data={custNaturePie}
                        angleField="value"
                        colorField="type"
                        radius={0.85}
                        height={280}
                        legend={{ position: 'bottom' }}
                      />
                    ) : (
                      <div className="text-center text-slate-400 py-12">暂无数据</div>
                    )}
                  </Card>
                </Col>
              </Row>

              <Card title="客户地图" size="small">
                <CustomerProvinceMap data={data.customers.map_by_province} height={360} />
              </Card>
            </>
          ) : null}
        </>
      )}
    </div>
  )
}
