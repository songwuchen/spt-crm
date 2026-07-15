// 仪表盘图表组件: 按 data_source 拉聚合数据并用 echarts 渲染(柱/条→bar, 折线→line, 饼→pie, 指标卡→number)。
import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty, Spin, Statistic } from 'antd'
import { dashboardApi } from '@/api/lowcodeDashboard'
import type { DashComponent, AggregateResult } from '@/types/lowcode'

const OP_CN: Record<string, string> = {
  count: '数量', count_distinct: '去重数', sum: '合计', avg: '平均', max: '最大', min: '最小',
}

export default function ChartWidget({ component }: { component: DashComponent }) {
  const [data, setData] = useState<AggregateResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const ds = component.data_source
  const isCrm = ds?.source === 'crm'
  const hasSource = isCrm ? !!ds?.entity : !!ds?.template_id
  const key = JSON.stringify(ds)

  useEffect(() => {
    if (!hasSource || (!ds.dimensions?.length && !ds.metrics?.length)) { setLoading(false); return }
    let alive = true
    setLoading(true); setErr(null)
    const p = isCrm
      ? dashboardApi.aggregateCrm({ entity: ds.entity!, dimensions: ds.dimensions, metrics: ds.metrics, filters: ds.filters })
      : dashboardApi.aggregate(ds)
    p.then((r) => { if (alive) { setData(r.data); setLoading(false) } })
      .catch((e) => { if (alive) { setErr((e as Error).message || '取数失败'); setLoading(false) } })
    return () => { alive = false }
  }, [key])  // eslint-disable-line react-hooks/exhaustive-deps

  const metricLabel = (i: number) => {
    const m = ds.metrics?.[i]
    return m ? OP_CN[m.op] || m.op : `指标${i + 1}`
  }

  const option = useMemo(() => {
    if (!data) return null
    const rows = data.rows || []
    const dims = data.dimensions || []
    const mets = data.metrics || []
    if (component.type === 'pie') {
      return {
        tooltip: { trigger: 'item' },
        legend: { type: 'scroll', bottom: 0 },
        series: [{ type: 'pie', radius: ['35%', '65%'], data: rows.map((r) => ({ name: String(r[dims[0]] ?? '—'), value: Number(r[mets[0]] ?? 0) })) }],
      }
    }
    const cats = rows.map((r) => String(r[dims[0]] ?? '—'))
    return {
      tooltip: { trigger: 'axis' },
      legend: { top: 0, data: mets.map((_, i) => metricLabel(i)) },
      grid: { left: 40, right: 16, top: 30, bottom: 30 },
      xAxis: { type: 'category', data: cats },
      yAxis: { type: 'value' },
      series: mets.map((mk, i) => ({ name: metricLabel(i), type: component.type === 'line' ? 'line' : 'bar', data: rows.map((r) => Number(r[mk] ?? 0)), smooth: true })),
    }
  }, [data, component.type])  // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}><Spin /></div>
  if (err) return <Empty description={err} image={Empty.PRESENTED_IMAGE_SIMPLE} />
  if (!hasSource) return <Empty description="未配置数据源" image={Empty.PRESENTED_IMAGE_SIMPLE} />

  if (component.type === 'number') {
    const val = data?.rows?.[0]?.[data.metrics?.[0]] ?? 0
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <Statistic title={metricLabel(0)} value={Number(val)} precision={2} />
      </div>
    )
  }

  if (!data?.rows?.length) return <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  return <ReactECharts option={option as object} style={{ height: '100%', width: '100%' }} notMerge lazyUpdate />
}
