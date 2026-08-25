/** 客户地图（按省统计）— 对齐简道云 map_chart，基于 ECharts 中国地图。 */
import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Spin } from 'antd'

const CHINA_GEO_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json'

let geoRegistered = false
let geoLoading: Promise<void> | null = null

function normalizeProvince(name: string): string {
  const s = (name || '').trim()
  if (!s || s === '未知') return s
  if (/自治区|特别行政区|市|省/.test(s)) return s
  const special: Record<string, string> = {
    北京: '北京市', 天津: '天津市', 上海: '上海市', 重庆: '重庆市',
    内蒙古: '内蒙古自治区', 广西: '广西壮族自治区', 西藏: '西藏自治区',
    宁夏: '宁夏回族自治区', 新疆: '新疆维吾尔自治区',
    香港: '香港特别行政区', 澳门: '澳门特别行政区',
  }
  if (special[s]) return special[s]
  return s.endsWith('省') ? s : `${s}省`
}

async function ensureChinaMap(): Promise<void> {
  if (geoRegistered) return
  if (!geoLoading) {
    geoLoading = (async () => {
      const res = await fetch(CHINA_GEO_URL)
      const geo = await res.json()
      const echarts = await import('echarts')
      echarts.registerMap('china', geo)
      geoRegistered = true
    })()
  }
  await geoLoading
}

export interface ProvinceCount { label: string; count: number }

export default function CustomerProvinceMap({
  data,
  height = 320,
}: {
  data: ProvinceCount[]
  height?: number
}) {
  const [ready, setReady] = useState(geoRegistered)
  const [err, setErr] = useState(false)

  useEffect(() => {
    let alive = true
    ensureChinaMap()
      .then(() => { if (alive) setReady(true) })
      .catch(() => { if (alive) setErr(true) })
    return () => { alive = false }
  }, [])

  const option = useMemo(() => {
    const rows = (data || []).map((d) => ({
      name: normalizeProvince(d.label),
      value: d.count,
    }))
    const max = rows.reduce((m, r) => Math.max(m, r.value), 0)
    return {
      tooltip: { trigger: 'item', formatter: '{b}<br/>客户数：{c}' },
      visualMap: {
        min: 0,
        max: Math.max(max, 1),
        left: 16,
        bottom: 16,
        text: ['高', '低'],
        calculable: true,
        inRange: { color: ['#E0F3F8', '#7FE7C6', '#0251A1'] },
      },
      series: [{
        type: 'map',
        map: 'china',
        roam: true,
        data: rows,
        emphasis: { label: { show: true } },
      }],
    }
  }, [data])

  if (err) {
    return <div className="text-center text-slate-400 py-12">地图加载失败</div>
  }
  if (!ready) {
    return (
      <div className="flex justify-center items-center" style={{ height }}>
        <Spin tip="正在加载地图…" />
      </div>
    )
  }
  if (!data?.length) {
    return <div className="text-center text-slate-400 py-12">暂无数据</div>
  }
  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge lazyUpdate />
}
