import { useState, useEffect } from 'react'
import { Table, Select, Tag, Spin, Input, Button } from 'antd'
import { DownloadOutlined, SearchOutlined } from '@ant-design/icons'
import { Pie, Column } from '@ant-design/charts'
import { customerApi } from '@/api/customer'
import { dashboardApi } from '@/api/dashboard'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'

interface CustomerRow {
  id: string; name: string; level?: string; industry?: string; region?: string
  status?: string; owner_name?: string; created_at: string
}

export default function CustomerLifecycleReport() {
  usePageTitle('客户生命周期报表')
  const [customers, setCustomers] = useState<CustomerRow[]>([])
  const [regionStats, setRegionStats] = useState<{ region: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [filterLevel, setFilterLevel] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    setLoading(true)
    Promise.all([
      customerApi.list({ pageNo: 1, pageSize: 100, level: filterLevel, keyword: keyword || undefined }).then((r: any) => r.data?.items || []),
      dashboardApi.customerRegionStats().then((r: any) => r.data || []).catch(() => []),
    ]).then(([custs, regions]) => {
      setCustomers(custs)
      setRegionStats(regions)
    }).finally(() => setLoading(false))
  }, [filterLevel, keyword])

  const total = customers.length
  const levelCounts = customers.reduce<Record<string, number>>((acc, c) => {
    const lv = c.level || '未分级'
    acc[lv] = (acc[lv] || 0) + 1
    return acc
  }, {})
  const industryCounts = customers.reduce<Record<string, number>>((acc, c) => {
    const ind = c.industry || '未知'
    acc[ind] = (acc[ind] || 0) + 1
    return acc
  }, {})

  const levelPie = Object.entries(levelCounts).map(([level, count]) => ({ type: level, value: count }))
  const industryData = Object.entries(industryCounts)
    .sort((a, b) => b[1] - a[1]).slice(0, 10)
    .map(([industry, count]) => ({ industry, count }))

  const levelColors: Record<string, string> = { A: 'red', B: 'orange', C: 'blue', D: 'default' }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold text-slate-900">客户生命周期报表</h1>
        <p className="text-sm text-slate-500 mt-1">客户等级分布、行业分析、地区覆盖</p>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: '客户总数', value: total, color: 'text-primary' },
          { label: 'A级客户', value: levelCounts['A'] || 0, color: 'text-red-600' },
          { label: 'B级客户', value: levelCounts['B'] || 0, color: 'text-amber-600' },
          { label: '覆盖地区', value: regionStats.length, color: 'text-indigo-600' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <div className="text-sm font-bold text-slate-400 uppercase">{kpi.label}</div>
            <div className={`text-2xl font-black mt-1 ${kpi.color}`}>{kpi.value}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-3 mb-4 flex-wrap">
        <Input.Search placeholder="搜索客户名称" allowClear style={{ width: 220 }}
          onSearch={(v) => setKeyword(v)} enterButton={<SearchOutlined />} />
        <Select placeholder="客户等级" allowClear style={{ width: 120 }} value={filterLevel} onChange={setFilterLevel}
          options={['A', 'B', 'C', 'D'].map(v => ({ label: `${v}级`, value: v }))} />
        <Button icon={<DownloadOutlined />} onClick={() => downloadFile(dashboardApi.exportExcelUrl({ report: 'customer_lifecycle' }), 'customer_lifecycle.xlsx')}>
          导出
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Level pie */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-slate-700 mb-4">客户等级分布</h3>
          {levelPie.length > 0 ? (
            <Pie data={levelPie} angleField="value" colorField="type" height={260}
              innerRadius={0.6}
              color={['#ef4444', '#f59e0b', '#3b82f6', '#94a3b8', '#6b7280']}
              label={{ type: 'spider' as any, content: '{name}: {value}' }}
              statistic={{ title: { content: '总计' }, content: { content: String(total) } }}
            />
          ) : <Spin className="flex justify-center py-8" />}
        </div>

        {/* Industry bar */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-slate-700 mb-4">行业分布 Top 10</h3>
          {industryData.length > 0 ? (
            <Column data={industryData} xField="industry" yField="count" height={260}
              color="#135bec"
              label={{ position: 'top' as const }}
            />
          ) : <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>}
        </div>
      </div>

      {/* Region chart */}
      {regionStats.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-6">
          <h3 className="text-sm font-bold text-slate-700 mb-4">地区分布</h3>
          <Column data={regionStats} xField="region" yField="count" height={220}
            color="#8b5cf6"
            label={{ position: 'top' as const }}
          />
        </div>
      )}

      {/* Customer table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={customers} loading={loading} size="small"
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
          columns={[
            { title: '客户名称', dataIndex: 'name', width: 200 },
            { title: '等级', dataIndex: 'level', width: 60, render: (v: string) => v ? <Tag color={levelColors[v] || 'default'}>{v}</Tag> : '-' },
            { title: '行业', dataIndex: 'industry', width: 120 },
            { title: '地区', dataIndex: 'region', width: 100 },
            { title: '负责人', dataIndex: 'owner_name', width: 100 },
            { title: '创建时间', dataIndex: 'created_at', width: 150, render: (v: string) => v ? v.slice(0, 10) : '-' },
          ]}
        />
      </div>
    </div>
  )
}
