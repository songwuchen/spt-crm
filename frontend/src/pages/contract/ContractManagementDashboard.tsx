/**

 * 合同管理仪表盘 — 布局对齐简道云「合同管理仪表盘」。

 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { useNavigate } from "react-router-dom";

import {
  Button,
  Card,
  Col,
  Row,
  Space,
  Spin,
  Table,
  Typography,
  message,
} from "antd";

import { ArrowLeftOutlined, UnorderedListOutlined } from "@ant-design/icons";

import { Area, Bar, DualAxes } from "@ant-design/charts";

import type { ColumnsType } from "antd/es/table";

import dayjs from "dayjs";

import { contractApi } from "@/api/contract";

import CustomerProvinceMap from "@/components/contract/CustomerProvinceMap";

import DashboardPieChart, {
  collapsePieItems,
} from "@/components/dashboard/DashboardPieChart";

import ContractDashboardFilterBar, {
  DEFAULT_CONTRACT_DASH_FILTERS,
  contractFiltersToQuery,
  type ContractDashboardFilters,
} from "@/components/dashboard/ContractDashboardFilterBar";

import { usePageTitle } from "@/hooks/usePageTitle";

const { Title, Text } = Typography;

export interface DashboardBucket {
  label: string;

  count: number;

  amount: number;
}

export interface DeptWorkloadRow {
  month: string;

  department: string;

  workload: string;

  count: number;

  amount: number;
}

export interface DeptMonthStatRow {
  month: string;

  department: string;

  count: number;

  amount: number;

  avg_amount: number;
}

export interface CustomerDashboardStats {
  total_count: number;

  founded_over_10y_count: number;

  by_industry: DashboardBucket[];

  by_nature: DashboardBucket[];

  by_province: DashboardBucket[];

  map_by_province: DashboardBucket[];
}

export interface ContractDashboardSummary {
  count: number;

  amount_total: number;

  year_amount: number;

  today_amount: number;

  card_date_from?: string | null;

  card_date_to?: string | null;

  by_year: DashboardBucket[];

  by_month: DashboardBucket[];

  by_department: DashboardBucket[];

  by_sales: DashboardBucket[];

  top_customers: DashboardBucket[];

  by_industry_contract: DashboardBucket[];

  dept_workload: DeptWorkloadRow[];

  dept_month_stats: DeptMonthStatRow[];

  customers: CustomerDashboardStats | null;
}

function fmtMoney(v: unknown) {
  const n = Number(v);

  if (!Number.isFinite(n)) return "0.00";

  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtMonthLabel(m: string) {
  if (/^\d{4}-\d{2}$/.test(m)) {
    const [y, mo] = m.split("-");

    return `${y}年${mo}月`;
  }

  return m;
}

function bucketsToPie(
  rows: DashboardBucket[],
  field: "count" | "amount",
  topN?: number,
): { type: string; value: number }[] {
  return collapsePieItems(
    rows.map((r) => ({ label: r.label, value: field === "count" ? r.count : r.amount })),
    topN,
  );
}

function DashCard({
  title,
  children,
  loading,
  className,
  bodyStyle,
}: {
  title: string;

  children: React.ReactNode;

  loading?: boolean;

  className?: string;

  bodyStyle?: React.CSSProperties;
}) {
  return (
    <Card
      title={
        <span className="text-sm font-semibold text-slate-800">{title}</span>
      }

      size="small"

      loading={loading}

      className={`h-full shadow-sm border-slate-200 ${className || ""}`}

      styles={{ header: { minHeight: 40, padding: "0 14px" }, body: bodyStyle }}
    >
      {children}
    </Card>
  );
}

function RankList({ items }: { items: { label: string; amount: number }[] }) {
  if (!items.length) {
    return (
      <div className="text-center text-slate-400 py-10 text-sm">暂无数据</div>
    );
  }

  return (
    <div className="divide-y divide-slate-100 max-h-[360px] overflow-y-auto">
      {items.map((it) => (
        <div
          key={it.label}
          className="flex items-center justify-between gap-3 py-2.5 px-1 text-sm"
        >
          <span className="truncate text-slate-700" title={it.label}>
            {it.label}
          </span>

          <span className="shrink-0 font-medium text-primary tabular-nums">
            {fmtMoney(it.amount)}
          </span>
        </div>
      ))}
    </div>
  );
}

function workloadRowSpans(rows: DeptWorkloadRow[]) {
  const monthSpan = new Map<number, number>();

  const deptSpan = new Map<number, number>();

  let i = 0;

  while (i < rows.length) {
    const m = rows[i].month;

    let j = i;

    while (j < rows.length && rows[j].month === m) j++;

    monthSpan.set(i, j - i);

    for (let k = i + 1; k < j; k++) monthSpan.set(k, 0);

    i = j;
  }

  i = 0;

  while (i < rows.length) {
    const key = `${rows[i].month}|${rows[i].department}`;

    let j = i;

    while (j < rows.length && `${rows[j].month}|${rows[j].department}` === key)
      j++;

    deptSpan.set(i, j - i);

    for (let k = i + 1; k < j; k++) deptSpan.set(k, 0);

    i = j;
  }

  return { monthSpan, deptSpan };
}

export default function ContractManagementDashboard() {
  usePageTitle("合同管理仪表盘");

  const nav = useNavigate();

  const [loading, setLoading] = useState(false);

  const [filters, setFilters] = useState<ContractDashboardFilters>(
    DEFAULT_CONTRACT_DASH_FILTERS,
  );

  const [debouncedCustomer, setDebouncedCustomer] = useState("");

  const [data, setData] = useState<ContractDashboardSummary | null>(null);

  const [workloadPage, setWorkloadPage] = useState(1);

  const [monthStatPage, setMonthStatPage] = useState(1);

  useEffect(() => {
    if (filters.customerOp === "in" || filters.customerOp === "nin") return;

    const t = window.setTimeout(
      () => setDebouncedCustomer(filters.customerName),
      400,
    );

    return () => window.clearTimeout(t);
  }, [filters.customerName, filters.customerOp]);

  const queryParams = useMemo(() => {
    const effective =
      filters.customerOp === "in" || filters.customerOp === "nin"
        ? filters
        : { ...filters, customerName: debouncedCustomer };

    return contractFiltersToQuery(effective);
  }, [filters, debouncedCustomer]);

  const load = useCallback(async () => {
    setLoading(true);

    try {
      const res = (await contractApi.dashboardSummary(queryParams)) as {
        data: ContractDashboardSummary;
      };

      setData(res.data);

      setWorkloadPage(1);

      setMonthStatPage(1);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })
        ?.response?.data?.message;

      message.error(msg || "加载仪表盘失败");
    } finally {
      setLoading(false);
    }
  }, [queryParams]);

  useEffect(() => {
    load();
  }, [load]);

  const monthChart = useMemo(
    () =>
      (data?.by_month || []).map((d) => ({
        month: fmtMonthLabel(d.label),

        amount: d.amount,
      })),

    [data],
  );

  const deptDualSource = useMemo(
    () =>
      (data?.by_department || []).map((d) => ({
        dept: d.label,

        count: d.count,

        amount: d.amount,
      })),

    [data],
  );

  const deptBar = useMemo(
    () =>
      [...(data?.by_department || [])]

        .sort((a, b) => b.amount - a.amount)

        .map((d) => ({ dept: d.label, amount: d.amount })),

    [data],
  );

  const deptPie = useMemo(
    () => bucketsToPie(data?.by_department || [], "amount"),
    [data],
  );

  const industryContractPie = useMemo(
    () => bucketsToPie(data?.by_industry_contract || [], "amount", 15),
    [data],
  );

  const custIndustryPie = useMemo(
    () => bucketsToPie(data?.customers?.by_industry || [], "count", 15),
    [data],
  );

  const custNaturePie = useMemo(
    () => bucketsToPie(data?.customers?.by_nature || [], "count", 15),
    [data],
  );

  const monthStatRows = data?.dept_month_stats || [];

  const monthStatSummary = useMemo(() => {
    const count = monthStatRows.reduce((s, r) => s + r.count, 0);

    const amount = monthStatRows.reduce((s, r) => s + r.amount, 0);

    return { count, amount, avg: count ? amount / count : 0 };
  }, [monthStatRows]);

  const workloadRows = data?.dept_workload || [];

  const { monthSpan, deptSpan } = useMemo(
    () => workloadRowSpans(workloadRows),
    [workloadRows],
  );

  const monthStatColumns: ColumnsType<DeptMonthStatRow> = [
    {
      title: "下卡日期",

      dataIndex: "month",

      width: 110,

      render: (v: string) => fmtMonthLabel(v),
    },

    { title: "部门", dataIndex: "department", ellipsis: true },

    { title: "合同数量", dataIndex: "count", width: 88, align: "right" },

    {
      title: "合同金额",
      dataIndex: "amount",
      width: 120,
      align: "right",

      render: (v: number) => fmtMoney(v),
    },

    {
      title: "平均金额",
      dataIndex: "avg_amount",
      width: 110,
      align: "right",

      render: (v: number) => fmtMoney(v),
    },
  ];

  const workloadColumns: ColumnsType<DeptWorkloadRow> = [
    {
      title: "下卡日期",

      dataIndex: "month",

      width: 100,

      render: (v: string) => fmtMonthLabel(v),

      onCell: (_, index) => ({
        rowSpan: index != null ? (monthSpan.get(index) ?? 1) : 1,
      }),
    },

    {
      title: "部门",

      dataIndex: "department",

      width: 120,

      ellipsis: true,

      onCell: (_, index) => ({
        rowSpan: index != null ? (deptSpan.get(index) ?? 1) : 1,
      }),
    },

    { title: "工作量", dataIndex: "workload", width: 90 },

    {
      title: "合同总金额",

      dataIndex: "amount",

      width: 120,

      align: "right",

      render: (v: number) => fmtMoney(v),
    },
  ];

  const provinceColumns: ColumnsType<DashboardBucket> = [
    { title: "地址", dataIndex: "label", ellipsis: true },

    { title: "客户数量", dataIndex: "count", width: 90, align: "right" },
  ];

  const currentYear = String(dayjs().year());

  return (
    <div className="flex flex-col gap-3 min-h-0 pb-4">
      <div className="flex justify-between items-center flex-wrap gap-2 shrink-0">
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => nav("/contracts")}
          >
            返回列表
          </Button>

          <Title level={4} style={{ margin: 0 }}>
            合同管理仪表盘
          </Title>
        </Space>

        <Button
          icon={<UnorderedListOutlined />}
          onClick={() => nav("/contracts")}
        >
          数据管理
        </Button>
      </div>

      <Card
        size="small"

        className="shrink-0 contract-dash-filter shadow-sm border-slate-200"

        styles={{ body: { padding: "12px 14px" } }}
      >
        <ContractDashboardFilterBar value={filters} onChange={setFilters} />
      </Card>

      {loading && !data ? (
        <div className="flex justify-center py-16">
          <Spin size="large" tip="正在加载…" />
        </div>
      ) : (
        <div className="space-y-3">
          {/* 第一行：左侧指标 + 右侧每月合同额 */}

          <Row gutter={[12, 12]} align="stretch">
            <Col xs={24} lg={6} xl={5}>
              <div className="flex flex-col gap-3 h-full">
                <DashCard
                  title="当天合同额"
                  loading={loading}
                  bodyStyle={{ padding: "16px 14px" }}
                >
                  <div className="text-3xl font-bold text-rose-500 tabular-nums leading-none">
                    {fmtMoney(data?.today_amount)}
                  </div>

                  <Text type="secondary" className="text-xs mt-2 block">
                    按今日下卡日期
                  </Text>
                </DashCard>

                <DashCard
                  title="年度合同额"
                  loading={loading}
                  bodyStyle={{ padding: "14px" }}
                >
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-slate-500">共计</span>

                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 text-sm font-semibold tabular-nums">
                        {fmtMoney(data?.year_amount)}
                      </span>
                    </div>

                    {(data?.by_year || []).slice(0, 3).map((y) => (
                      <div
                        key={y.label}
                        className="flex items-center gap-2 flex-wrap"
                      >
                        <span className="text-xs text-slate-500 w-10">
                          {y.label}
                        </span>

                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-blue-50 text-primary text-sm font-medium tabular-nums">
                          {fmtMoney(y.amount)}
                        </span>
                      </div>
                    ))}

                    {!data?.by_year?.length && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">
                          {currentYear}
                        </span>

                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-blue-50 text-primary text-sm font-medium tabular-nums">
                          {fmtMoney(data?.year_amount)}
                        </span>
                      </div>
                    )}
                  </div>
                </DashCard>
              </div>
            </Col>

            <Col xs={24} lg={18} xl={19}>
              <DashCard
                title="每月合同额"
                loading={loading}
                bodyStyle={{ padding: "8px 12px 4px" }}
              >
                {monthChart.length ? (
                  <Area
                    data={monthChart}

                    xField="month"

                    yField="amount"

                    height={240}

                    style={{
                      fill: "linear-gradient(-90deg, white 0%, rgba(19,127,236,0.35) 100%)",
                    }}

                    line={{ style: { stroke: "#137fec", lineWidth: 2 } }}

                    point={{ size: 3 }}

                    axis={{
                      x: { label: { autoRotate: true } },
                      y: { title: "合同金额（元）" },
                    }}
                  />
                ) : (
                  <div className="text-center text-slate-400 py-16 text-sm">
                    暂无数据
                  </div>
                )}
              </DashCard>
            </Col>
          </Row>

          {/* 第二行：部门占比 + 双轴图 */}

          <Row gutter={[12, 12]} align="stretch">
            <Col xs={24} lg={9}>
              <DashCard title="部门合同占比" loading={loading}>
                <DashboardPieChart
                  data={deptPie}
                  height={300}
                  innerRadius={0.52}
                  legendPosition="bottom"
                  minSliceLabelPct={6}
                  valueFormatter={(v) => fmtMoney(v)}
                />
              </DashCard>
            </Col>

            <Col xs={24} lg={15}>
              <DashCard title="合同数量和金额" loading={loading}>
                {deptDualSource.length ? (
                  <DualAxes
                    xField="dept"

                    height={280}

                    legend={{ color: { position: "top" } }}

                    scale={{ y: { nice: true } }}

                    axis={{ x: { label: { autoRotate: true } } }}

                    children={[
                      {
                        data: deptDualSource,

                        type: "area",

                        yField: "count",

                        style: {
                          fill: "linear-gradient(-90deg, white 0%, rgba(82,196,26,0.35) 100%)",
                        },

                        axis: { y: { title: "合同数量" } },
                      },

                      {
                        data: deptDualSource,

                        type: "line",

                        yField: "amount",

                        style: { stroke: "#fa8c16", lineWidth: 2 },

                        axis: {
                          y: { position: "right", title: "合同金额（元）" },
                        },
                      },
                    ]}
                  />
                ) : (
                  <div className="text-center text-slate-400 py-16 text-sm">
                    暂无数据
                  </div>
                )}
              </DashCard>
            </Col>
          </Row>

          {/* 第三行：部门排序 + 业务人员 + 前10客户 */}

          <Row gutter={[12, 12]} align="stretch">
            <Col xs={24} lg={8}>
              <DashCard title="部门排序" loading={loading}>
                {deptBar.length ? (
                  <Bar
                    data={deptBar}

                    xField="amount"

                    yField="dept"

                    height={360}

                    direction="horizontal"

                    style={{ fill: "#52c41a" }}

                    axis={{ x: { title: "合同金额（元）" } }}

                    label={{
                      text: "amount",
                      position: "right",
                      formatter: (v: string) => fmtMoney(v),
                    }}
                  />
                ) : (
                  <div className="text-center text-slate-400 py-16 text-sm">
                    暂无数据
                  </div>
                )}
              </DashCard>
            </Col>

            <Col xs={24} lg={8}>
              <DashCard title="业务人员年度合同排序" loading={loading}>
                <RankList
                  items={(data?.by_sales || []).map((d) => ({
                    label: d.label,
                    amount: d.amount,
                  }))}
                />
              </DashCard>
            </Col>

            <Col xs={24} lg={8}>
              <DashCard title="前10大客户" loading={loading}>
                <RankList
                  items={(data?.top_customers || []).map((d) => ({
                    label: d.label,
                    amount: d.amount,
                  }))}
                />
              </DashCard>
            </Col>
          </Row>

          {/* 第四行：合同数量金额表 + 部门工作量 */}

          <Row gutter={[12, 12]} align="stretch">
            <Col xs={24} lg={12}>
              <DashCard
                title="合同数量和金额"
                loading={loading}
                bodyStyle={{ padding: 0 }}
              >
                <Table<DeptMonthStatRow>
                  rowKey={(r) => `${r.month}-${r.department}`}

                  size="small"

                  columns={monthStatColumns}

                  dataSource={monthStatRows}

                  pagination={{
                    current: monthStatPage,

                    pageSize: 10,

                    showSizeChanger: false,

                    onChange: (p) => setMonthStatPage(p),

                    size: "small",
                  }}

                  summary={() =>
                    monthStatRows.length ? (
                      <Table.Summary fixed>
                        <Table.Summary.Row className="bg-slate-50 font-medium">
                          <Table.Summary.Cell index={0} colSpan={2}>
                            汇总
                          </Table.Summary.Cell>

                          <Table.Summary.Cell index={2} align="right">
                            {monthStatSummary.count}
                          </Table.Summary.Cell>

                          <Table.Summary.Cell index={3} align="right">
                            {fmtMoney(monthStatSummary.amount)}
                          </Table.Summary.Cell>

                          <Table.Summary.Cell index={4} align="right">
                            {fmtMoney(monthStatSummary.avg)}
                          </Table.Summary.Cell>
                        </Table.Summary.Row>
                      </Table.Summary>
                    ) : null
                  }

                  scroll={{ x: 520, y: 320 }}
                />
              </DashCard>
            </Col>

            <Col xs={24} lg={12}>
              <DashCard
                title="部门工作量统计"
                loading={loading}
                bodyStyle={{ padding: 0 }}
              >
                <Table<DeptWorkloadRow>
                  rowKey={(r) => `${r.month}-${r.department}-${r.workload}`}

                  size="small"

                  columns={workloadColumns}

                  dataSource={workloadRows}

                  pagination={{
                    current: workloadPage,

                    pageSize: 10,

                    showSizeChanger: false,

                    onChange: (p) => setWorkloadPage(p),

                    size: "small",
                  }}

                  scroll={{ x: 480, y: 320 }}
                />
              </DashCard>
            </Col>
          </Row>

          {/* 行业合同额 */}

          <DashCard title="行业合同额" loading={loading}>
            <DashboardPieChart
              data={industryContractPie}
              height={300}
              legendPosition="right"
              valueFormatter={(v) => fmtMoney(v)}
            />
          </DashCard>

          {/* 客户区块 */}

          {data?.customers ? (
            <>
              <Row gutter={[12, 12]} align="stretch">
                <Col xs={24} md={8} lg={5}>
                  <div className="flex flex-col gap-3 h-full">
                    <DashCard
                      title="客户数量"
                      bodyStyle={{ padding: "20px 14px", textAlign: "center" }}
                    >
                      <div className="text-4xl font-bold text-slate-800 tabular-nums">
                        {data.customers.total_count.toLocaleString("zh-CN")}
                      </div>
                    </DashCard>

                    <DashCard
                      title="成立十年以上的客户"
                      bodyStyle={{ padding: "20px 14px", textAlign: "center" }}
                    >
                      <div className="text-4xl font-bold text-slate-800 tabular-nums">
                        {data.customers.founded_over_10y_count.toLocaleString(
                          "zh-CN",
                        )}
                      </div>
                    </DashCard>
                  </div>
                </Col>

                <Col xs={24} md={8} lg={7}>
                  <DashCard title="省市分布" bodyStyle={{ padding: 0 }}>
                    <Table
                      rowKey="label"

                      size="small"

                      pagination={{
                        pageSize: 8,
                        showSizeChanger: false,
                        size: "small",
                      }}

                      columns={provinceColumns}

                      dataSource={data.customers.by_province}

                      scroll={{ y: 280 }}
                    />
                  </DashCard>
                </Col>

                <Col xs={24} md={8} lg={12}>
                  <div className="flex flex-col gap-3 h-full">
                    <DashCard title="所属行业">
                      <DashboardPieChart
                        data={custIndustryPie}
                        height={280}
                        legendPosition="bottom"
                      />
                    </DashCard>
                    <DashCard title="客户性质">
                      <DashboardPieChart
                        data={custNaturePie}
                        height={280}
                        legendPosition="bottom"
                      />
                    </DashCard>
                  </div>
                </Col>
              </Row>

              <DashCard title="客户地图">
                <CustomerProvinceMap
                  data={data.customers.map_by_province}
                  height={360}
                />
              </DashCard>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
