import { useMemo } from 'react'

import Icon from '@/components/Icon'
interface RegionMapProps {
  data: Array<{ region: string; count: number }>
  /** 点击大区回调：regionCode = 该大区各省份编码前缀(逗号分隔)，regionName = 大区名(用于兼容 legacy 文本地区过滤) */
  onRegionClick?: (regionCode: string, regionName: string) => void
}

// Simplified China regions with approximate SVG positions.
// codes = 该大区所含省级行政区划的 2 位 GB 编码前缀，点击时用于按 region_code 前缀过滤。
const REGIONS: Array<{ name: string; keywords: string[]; codes: string[]; x: number; y: number }> = [
  { name: '华北', keywords: ['华北', '北京', '天津', '河北', '山西', '内蒙古'], codes: ['11', '12', '13', '14', '15'], x: 280, y: 100 },
  { name: '东北', keywords: ['东北', '辽宁', '吉林', '黑龙江'], codes: ['21', '22', '23'], x: 360, y: 60 },
  { name: '华东', keywords: ['华东', '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东'], codes: ['31', '32', '33', '34', '35', '36', '37'], x: 340, y: 200 },
  { name: '华中', keywords: ['华中', '河南', '湖北', '湖南'], codes: ['41', '42', '43'], x: 270, y: 220 },
  { name: '华南', keywords: ['华南', '广东', '广西', '海南', '深圳'], codes: ['44', '45', '46'], x: 290, y: 310 },
  { name: '西南', keywords: ['西南', '重庆', '四川', '贵州', '云南', '西藏'], codes: ['50', '51', '52', '53', '54'], x: 170, y: 270 },
  { name: '西北', keywords: ['西北', '陕西', '甘肃', '青海', '宁夏', '新疆'], codes: ['61', '62', '63', '64', '65'], x: 120, y: 120 },
  { name: '港澳台', keywords: ['港澳台', '香港', '澳门', '台湾'], codes: ['71', '81', '82'], x: 350, y: 310 },
]

function matchRegion(regionStr: string): string {
  if (!regionStr) return '其他'
  for (const r of REGIONS) {
    for (const kw of r.keywords) {
      if (regionStr.includes(kw)) return r.name
    }
  }
  return '其他'
}

export default function RegionMap({ data, onRegionClick }: RegionMapProps) {
  const regionCounts = useMemo(() => {
    const map = new Map<string, number>()
    for (const d of data) {
      const rName = matchRegion(d.region)
      map.set(rName, (map.get(rName) || 0) + d.count)
    }
    return map
  }, [data])

  const maxCount = Math.max(...regionCounts.values(), 1)

  const getColor = (count: number) => {
    if (count === 0) return '#f1f5f9'
    const ratio = count / maxCount
    if (ratio <= 0.25) return '#bfdbfe'
    if (ratio <= 0.5) return '#60a5fa'
    if (ratio <= 0.75) return '#2563eb'
    return '#1d4ed8'
  }

  const getSize = (count: number) => {
    return Math.max(24, Math.min(60, 24 + (count / maxCount) * 36))
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
        <Icon name="map" className="text-blue-500" style={{ fontSize: 18 }} />
        客户区域分布
      </h3>
      <div className="relative" style={{ width: '100%', maxWidth: 460, height: 380, margin: '0 auto' }}>
        {/* Simple outline */}
        <svg viewBox="0 0 460 380" className="w-full h-full">
          {/* China outline (simplified) */}
          <path d="M100,50 L180,30 L260,40 L340,20 L400,50 L420,100 L400,140 L380,180 L400,220 L380,260 L340,300 L300,340 L250,360 L200,340 L160,300 L120,260 L80,220 L60,180 L80,140 L100,100 Z"
            fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1.5" />

          {/* Region bubbles */}
          {REGIONS.map((r) => {
            const count = regionCounts.get(r.name) || 0
            const size = getSize(count)
            const color = getColor(count)
            return (
              <g key={r.name}
                className="cursor-pointer transition-transform hover:scale-110"
                onClick={() => onRegionClick?.(r.codes.join(','), r.name)}
              >
                <circle cx={r.x} cy={r.y} r={size / 2} fill={color} opacity={0.85}
                  stroke="#fff" strokeWidth="2" />
                <text x={r.x} y={r.y - 4} textAnchor="middle" fill={count > 0 ? '#fff' : '#94a3b8'}
                  fontSize="10" fontWeight="bold">{r.name}</text>
                {count > 0 && (
                  <text x={r.x} y={r.y + 10} textAnchor="middle" fill="#fff"
                    fontSize="12" fontWeight="900">{count}</text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-2">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full" style={{ background: '#bfdbfe' }} />
          <span className="text-[12px] text-slate-400">少</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full" style={{ background: '#60a5fa' }} />
          <span className="text-[12px] text-slate-400">中</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full" style={{ background: '#1d4ed8' }} />
          <span className="text-[12px] text-slate-400">多</span>
        </div>
      </div>
    </div>
  )
}
