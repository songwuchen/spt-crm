import { useMemo } from 'react'

interface Props {
  tags: string[]
  onClick?: (tag: string) => void
}

const TAG_COLORS = [
  'bg-blue-50 text-blue-700 border-blue-200',
  'bg-emerald-50 text-emerald-700 border-emerald-200',
  'bg-amber-50 text-amber-700 border-amber-200',
  'bg-purple-50 text-purple-700 border-purple-200',
  'bg-rose-50 text-rose-700 border-rose-200',
  'bg-indigo-50 text-indigo-700 border-indigo-200',
  'bg-teal-50 text-teal-700 border-teal-200',
  'bg-orange-50 text-orange-700 border-orange-200',
]

export default function CustomerTagCloud({ tags, onClick }: Props) {
  const tagCounts = useMemo(() => {
    const map = new Map<string, number>()
    tags.forEach((t) => map.set(t, (map.get(t) || 0) + 1))
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([tag, count]) => ({ tag, count }))
  }, [tags])

  if (tagCounts.length === 0) {
    return <div className="text-center py-6 text-slate-400 text-sm">暂无标签数据</div>
  }

  const maxCount = tagCounts[0]?.count || 1

  return (
    <div className="flex flex-wrap gap-2 items-center justify-center">
      {tagCounts.map(({ tag, count }, i) => {
        const ratio = count / maxCount
        const sizeClass = ratio > 0.75 ? 'text-lg px-4 py-2' :
          ratio > 0.5 ? 'text-base px-3 py-1.5' :
          ratio > 0.25 ? 'text-sm px-2.5 py-1' :
          'text-sm px-2 py-0.5'
        const colorClass = TAG_COLORS[i % TAG_COLORS.length]
        return (
          <button
            key={tag}
            onClick={() => onClick?.(tag)}
            className={`inline-flex items-center gap-1 rounded-full border font-bold transition-transform hover:scale-105 ${sizeClass} ${colorClass}`}
          >
            {tag}
            <span className="opacity-60 font-normal">({count})</span>
          </button>
        )
      })}
    </div>
  )
}
