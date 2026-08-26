/**
 * 仪表盘饼图/环图 — 保留 Pie 组件，通过关闭扇区标签 + 分页图例解决模糊重叠。
 */
import { useMemo } from 'react'
import { Pie } from '@ant-design/charts'

export interface PieChartItem {
  type: string
  value: number
}

export function collapsePieItems(
  rows: { label: string; value: number }[],
  topN?: number,
): PieChartItem[] {
  const sorted = [...rows].filter((r) => r.value > 0).sort((a, b) => b.value - a.value)
  if (!topN || sorted.length <= topN) {
    return sorted.map((r) => ({ type: r.label, value: r.value }))
  }
  const top = sorted.slice(0, topN)
  const rest = sorted.slice(topN).reduce((s, x) => s + x.value, 0)
  const out = top.map((r) => ({ type: r.label, value: r.value }))
  if (rest > 0) out.push({ type: '其他', value: rest })
  return out
}

interface Props {
  data: PieChartItem[]
  height?: number
  /** 0 为饼图，>0 为环图 */
  innerRadius?: number
  legendPosition?: 'right' | 'bottom'
  /** 扇区外仅显示占比 ≥ 该值的百分比（undefined 则不显示扇区文字） */
  minSliceLabelPct?: number
  valueFormatter?: (v: number) => string
}

export default function DashboardPieChart({
  data,
  height = 280,
  innerRadius = 0,
  legendPosition = 'bottom',
  minSliceLabelPct,
  valueFormatter,
}: Props) {
  const total = useMemo(
    () => data.reduce((s, d) => s + d.value, 0),
    [data],
  )

  if (!data.length || total <= 0) {
    return <div className="text-center text-slate-400 py-12 text-sm">暂无数据</div>
  }

  const fmt = valueFormatter || ((v: number) => v.toLocaleString('zh-CN'))

  const legendItemText = (datum: unknown, index?: number) => {
    let name = ''
    if (typeof datum === 'string') {
      name = datum
    } else if (datum && typeof datum === 'object') {
      const d = datum as { label?: string; id?: string; value?: string }
      name = d.label ?? d.id ?? d.value ?? ''
    }
    const row = (typeof index === 'number' ? data[index] : undefined)
      ?? data.find((d) => d.type === name)
    if (!row) return name
    const pct = total ? ((row.value / total) * 100).toFixed(1) : '0'
    const display = row.type || name
    if (legendPosition === 'right') {
      const short = display.length > 12 ? `${display.slice(0, 12)}…` : display
      return `${short}  ${pct}%`
    }
    return `${display}  ${fmt(row.value)} (${pct}%)`
  }

  const labelConfig = minSliceLabelPct != null
    ? {
        text: (d: { type: string; value: number }) => {
          const pct = (d.value / total) * 100
          if (pct < minSliceLabelPct) return ''
          return `${pct.toFixed(1)}%`
        },
        position: 'outside' as const,
        style: { fontSize: 11, fill: '#64748b' },
      }
    : false

  const legendConfig = legendPosition === 'right'
    ? {
        color: {
          position: 'right' as const,
          layout: { justifyContent: 'center' as const },
          maxRows: 14,
          flipPage: true,
          itemLabelText: legendItemText,
        },
      }
    : {
        color: {
          position: 'bottom' as const,
          flipPage: true,
          maxRows: 2,
          itemLabelText: legendItemText,
        },
      }

  return (
    <Pie
      data={data}
      angleField="value"
      colorField="type"
      radius={0.88}
      innerRadius={innerRadius > 0 ? innerRadius : undefined}
      height={height}
      label={labelConfig}
      legend={legendConfig}
      tooltip={{
        title: (d: { type: string }) => d.type,
        items: [{
          field: 'value',
          name: '数值',
          valueFormatter: (v: number) => {
            const pct = total ? ((v / total) * 100).toFixed(1) : '0'
            return `${fmt(v)} (${pct}%)`
          },
        }],
      }}
    />
  )
}
