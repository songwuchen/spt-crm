// 仪表盘图表组件: 按 data_source 拉聚合数据并渲染。
// 支持: 柱/条形(bar)、折线(line)、面积(area)、饼(pie)、漏斗(funnel)、雷达(radar)、
//       散点(scatter)、仪表盘(gauge)、双轴(dual_axis)、指标卡(number)、透视表(pivot)。
// 多序列: 配置第二维度(dim_1)时,bar/line/area/pivot 会按第二维度拆分序列。
import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty, Spin, Statistic, Table } from 'antd'
import { dashboardApi } from '@/api/lowcodeDashboard'
import type { DashComponent, AggregateResult } from '@/types/lowcode'

const OP_CN: Record<string, string> = {
  count: '数量', count_distinct: '去重数', sum: '合计', avg: '平均', max: '最大', min: '最小',
}

const num = (v: unknown) => (v == null ? 0 : Number(v) || 0)
const str = (v: unknown) => String(v ?? '—')

// 保序去重
function distinct(values: unknown[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const v of values) { const s = str(v); if (!seen.has(s)) { seen.add(s); out.push(s) } }
  return out
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

  const model = useMemo(() => {
    if (!data) return null
    const rows = data.rows || []
    const dims = data.dimensions || []
    const mets = data.metrics || []
    const type = component.type
    const cat0 = distinct(rows.map((r) => r[dims[0]]))
    const twoDim = dims.length >= 2

    // 双维度: 以 dim0 为 X 轴分类, dim1 各值为序列, 值取 metric0
    if (twoDim && ['bar', 'line', 'area', 'pivot'].includes(type)) {
      const series = distinct(rows.map((r) => r[dims[1]]))
      const cell: Record<string, Record<string, number>> = {}
      for (const r of rows) {
        const a = str(r[dims[0]]); const b = str(r[dims[1]])
        ;(cell[a] ||= {})[b] = num(r[mets[0]])
      }
      return { kind: 'multi', cat0, series, cell, dims, mets, type }
    }
    return { kind: 'single', rows, cat0, dims, mets, type }
  }, [data, component.type])  // eslint-disable-line react-hooks/exhaustive-deps

  const option = useMemo(() => {
    if (!model || !data) return null
    const { type } = model
    const rows = data.rows || []
    const dims = data.dimensions || []
    const mets = data.metrics || []

    // ---- 多序列(双维度) ----
    if (model.kind === 'multi') {
      const { cat0, series, cell } = model as { cat0: string[]; series: string[]; cell: Record<string, Record<string, number>> }
      const stack = type === 'area'
      return {
        tooltip: { trigger: 'axis' },
        legend: { type: 'scroll', top: 0, data: series },
        grid: { left: 44, right: 16, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: cat0 },
        yAxis: { type: 'value' },
        series: series.map((s) => ({
          name: s, type: type === 'line' || type === 'area' ? 'line' : 'bar',
          stack: stack ? 'total' : undefined, areaStyle: type === 'area' ? {} : undefined, smooth: true,
          data: cat0.map((c) => cell[c]?.[s] ?? 0),
        })),
      }
    }

    // ---- 单维度 ----
    const cats = model.cat0
    if (type === 'pie' || type === 'funnel') {
      const d = rows.map((r) => ({ name: str(r[dims[0]]), value: num(r[mets[0]]) }))
      return type === 'pie'
        ? { tooltip: { trigger: 'item' }, legend: { type: 'scroll', bottom: 0 }, series: [{ type: 'pie', radius: ['35%', '65%'], data: d }] }
        : { tooltip: { trigger: 'item' }, legend: { type: 'scroll', bottom: 0 }, series: [{ type: 'funnel', left: '10%', width: '80%', data: d }] }
    }
    if (type === 'radar') {
      const maxVal = Math.max(1, ...rows.flatMap((r) => mets.map((m) => num(r[m]))))
      return {
        tooltip: {}, legend: { top: 0, data: mets.map((_, i) => metricLabel(i)) },
        radar: { indicator: cats.map((c) => ({ name: c, max: maxVal })) },
        series: [{ type: 'radar', data: mets.map((m, i) => ({ name: metricLabel(i), value: rows.map((r) => num(r[m])) })) }],
      }
    }
    if (type === 'scatter') {
      const mx = mets[0]; const my = mets[1] || mets[0]
      return {
        tooltip: { trigger: 'item' },
        grid: { left: 44, right: 16, top: 20, bottom: 30 },
        xAxis: { type: 'value', name: metricLabel(0) }, yAxis: { type: 'value', name: mets[1] ? metricLabel(1) : '' },
        series: [{ type: 'scatter', symbolSize: 12, data: rows.map((r) => [num(r[mx]), num(r[my]), str(r[dims[0]])]) }],
      }
    }
    if (type === 'dual_axis') {
      const cats2 = rows.map((r) => str(r[dims[0]]))
      return {
        tooltip: { trigger: 'axis' }, legend: { top: 0, data: [metricLabel(0), mets[1] ? metricLabel(1) : ''] },
        grid: { left: 44, right: 44, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: cats2 },
        yAxis: [{ type: 'value', name: metricLabel(0) }, { type: 'value', name: mets[1] ? metricLabel(1) : '' }],
        series: [
          { name: metricLabel(0), type: 'bar', data: rows.map((r) => num(r[mets[0]])) },
          ...(mets[1] ? [{ name: metricLabel(1), type: 'line', yAxisIndex: 1, smooth: true, data: rows.map((r) => num(r[mets[1]])) }] : []),
        ],
      }
    }
    // bar / line / area(单维度, 多指标)
    const stack = type === 'area'
    return {
      tooltip: { trigger: 'axis' },
      legend: { top: 0, data: mets.map((_, i) => metricLabel(i)) },
      grid: { left: 44, right: 16, top: 30, bottom: 30 },
      xAxis: { type: 'category', data: cats },
      yAxis: { type: 'value' },
      series: mets.map((mk, i) => ({
        name: metricLabel(i), type: type === 'line' || type === 'area' ? 'line' : 'bar',
        areaStyle: type === 'area' ? {} : undefined, stack: stack ? 'total' : undefined, smooth: true,
        data: rows.map((r) => num(r[mk])),
      })),
    }
  }, [model, data])  // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}><Spin /></div>
  if (err) return <Empty description={err} image={Empty.PRESENTED_IMAGE_SIMPLE} />
  if (!hasSource) return <Empty description="未配置数据源" image={Empty.PRESENTED_IMAGE_SIMPLE} />

  // ---- 指标卡 ----
  if (component.type === 'number') {
    const val = data?.rows?.[0]?.[data.metrics?.[0]] ?? 0
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <Statistic title={metricLabel(0)} value={Number(val)} precision={2} />
      </div>
    )
  }

  if (!data?.rows?.length) return <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />

  // 散点/双轴需要两个指标, 否则会退化成对角散点/丢失第二序列 —— 明确提示而非误导渲染。
  if ((component.type === 'scatter' || component.type === 'dual_axis') && (data.metrics?.length ?? 0) < 2) {
    return <Empty description="该图表需要两个指标(如散点的 X/Y、双轴的柱+线)" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  // ---- 仪表盘(单值) ----
  if (component.type === 'gauge') {
    const rows = data.rows
    const total = rows.reduce((s, r) => s + num(r[data.metrics[0]]), 0)
    const max = Math.max(1, ...rows.map((r) => num(r[data.metrics[0]]))) * (rows.length > 1 ? rows.length : 1.2)
    const gaugeOpt = {
      series: [{
        type: 'gauge', min: 0, max: Math.ceil(max), progress: { show: true },
        detail: { valueAnimation: true, formatter: '{value}', fontSize: 18 },
        data: [{ value: Number(total.toFixed(2)), name: metricLabel(0) }],
      }],
    }
    return <ReactECharts option={gaugeOpt} style={{ height: '100%', width: '100%' }} notMerge lazyUpdate />
  }

  // ---- 透视表 ----
  if (component.type === 'pivot') {
    const dims = data.dimensions; const mets = data.metrics
    if (model?.kind === 'multi') {
      const { cat0, series, cell } = model as { cat0: string[]; series: string[]; cell: Record<string, Record<string, number>> }
      const columns = [{ title: '', dataIndex: '__row', fixed: 'left' as const },
        ...series.map((s) => ({ title: s, dataIndex: s }))]
      const dataSource = cat0.map((c, i) => ({ key: i, __row: c, ...Object.fromEntries(series.map((s) => [s, cell[c]?.[s] ?? 0])) }))
      return <div style={{ height: '100%', overflow: 'auto' }}><Table size="small" columns={columns} dataSource={dataSource} pagination={false} scroll={{ x: true }} /></div>
    }
    const columns = [{ title: '维度', dataIndex: '__dim', fixed: 'left' as const },
      ...mets.map((m, i) => ({ title: metricLabel(i), dataIndex: m }))]
    const dataSource = data.rows.map((r, i) => ({ key: i, __dim: str(r[dims[0]]), ...Object.fromEntries(mets.map((m) => [m, num(r[m])])) }))
    return <div style={{ height: '100%', overflow: 'auto' }}><Table size="small" columns={columns} dataSource={dataSource} pagination={false} scroll={{ x: true }} /></div>
  }

  return <ReactECharts option={option as object} style={{ height: '100%', width: '100%' }} notMerge lazyUpdate />
}
