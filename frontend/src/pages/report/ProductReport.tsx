import { useState, useEffect } from 'react'
import { Table, DatePicker, Select, Tag, Spin } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { Column, Pie } from '@ant-design/charts'
import { productApi } from '@/api/product'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'

interface ProductStat {
  product_code: string; name: string; category_name?: string
  unit_price: number | null; usage_count: number; is_active: boolean
}

export default function ProductReport() {
  usePageTitle('产品销售报表')
  const [products, setProducts] = useState<ProductStat[]>([])
  const [loading, setLoading] = useState(true)
  const [filterActive, setFilterActive] = useState<boolean | undefined>(true)

  useEffect(() => {
    setLoading(true)
    productApi.list({ pageNo: 1, pageSize: 100, is_active: filterActive })
      .then((r: any) => setProducts(r.data?.items || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filterActive])

  const totalProducts = products.length
  const activeCount = products.filter(p => p.is_active).length
  const citedCount = products.filter(p => p.usage_count > 0).length
  const totalCitations = products.reduce((s, p) => s + p.usage_count, 0)

  // Top 10 by usage
  const topUsage = [...products].sort((a, b) => b.usage_count - a.usage_count).slice(0, 10)

  // Active vs inactive pie
  const activePie = [
    { type: '在售', value: activeCount },
    { type: '停售', value: totalProducts - activeCount },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold text-slate-900">产品销售报表</h1>
        <p className="text-sm text-slate-500 mt-1">产品引用分析、活跃度、报价覆盖率</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: '产品总数', value: totalProducts, color: 'text-primary' },
          { label: '在售产品', value: activeCount, color: 'text-emerald-600' },
          { label: '被引用产品', value: citedCount, color: 'text-amber-600' },
          { label: '引用总次数', value: totalCitations, color: 'text-indigo-600' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <div className="text-xs font-bold text-slate-400 uppercase">{kpi.label}</div>
            <div className={`text-2xl font-black mt-1 ${kpi.color}`}>{kpi.value}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-3 mb-4">
        <Select value={filterActive} onChange={setFilterActive} style={{ width: 120 }} allowClear placeholder="状态"
          options={[{ label: '在售', value: true }, { label: '停售', value: false }]} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Top 10 chart */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-slate-700 mb-4">引用次数 Top 10</h3>
          {topUsage.length > 0 ? (
            <Column data={topUsage.map(p => ({ name: p.name, count: p.usage_count }))}
              xField="name" yField="count" height={260}
              color="#135bec"
              label={{ position: 'top' as const }}
            />
          ) : <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>}
        </div>

        {/* Active pie */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-slate-700 mb-4">产品状态分布</h3>
          <Pie data={activePie} angleField="value" colorField="type" height={260}
            color={['#10b981', '#94a3b8']}
            innerRadius={0.6}
            label={{ type: 'spider' as any, content: '{name}: {value}' }}
            statistic={{ title: { content: '总计' }, content: { content: String(totalProducts) } }}
          />
        </div>
      </div>

      {/* Product table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="product_code" dataSource={products} loading={loading} size="small"
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
          columns={[
            { title: '产品编码', dataIndex: 'product_code', width: 120, render: (v: string) => <span className="font-mono text-xs">{v}</span> },
            { title: '名称', dataIndex: 'name', width: 200 },
            { title: '单价', dataIndex: 'unit_price', width: 100, render: (v: number | null) => v != null ? `¥${v.toLocaleString()}` : '-' },
            { title: '引用次数', dataIndex: 'usage_count', width: 100, sorter: (a: ProductStat, b: ProductStat) => a.usage_count - b.usage_count,
              render: (v: number) => <span className={v > 0 ? 'font-bold text-primary' : 'text-slate-400'}>{v}</span> },
            { title: '状态', dataIndex: 'is_active', width: 80, render: (v: boolean) => v ? <Tag color="success">在售</Tag> : <Tag>停售</Tag> },
          ]}
        />
      </div>
    </div>
  )
}
