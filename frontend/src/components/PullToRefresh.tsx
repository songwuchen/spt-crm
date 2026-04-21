import { useState, useRef, useCallback } from 'react'

interface Props {
  onRefresh: () => Promise<void>
  children: React.ReactNode
  threshold?: number
}

export default function PullToRefresh({ onRefresh, children, threshold = 60 }: Props) {
  const [pulling, setPulling] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [pullDistance, setPullDistance] = useState(0)
  const startY = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (containerRef.current && containerRef.current.scrollTop === 0) {
      startY.current = e.touches[0].clientY
      setPulling(true)
    }
  }, [])

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!pulling || refreshing) return
    const diff = e.touches[0].clientY - startY.current
    if (diff > 0) {
      setPullDistance(Math.min(diff * 0.5, threshold * 1.5))
    }
  }, [pulling, refreshing, threshold])

  const handleTouchEnd = useCallback(async () => {
    if (!pulling) return
    setPulling(false)
    if (pullDistance >= threshold && !refreshing) {
      setRefreshing(true)
      try {
        await onRefresh()
      } finally {
        setRefreshing(false)
      }
    }
    setPullDistance(0)
  }, [pulling, pullDistance, threshold, refreshing, onRefresh])

  return (
    <div
      ref={containerRef}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      className="relative overflow-auto"
      style={{ height: '100%' }}
    >
      <div
        className="flex items-center justify-center text-sm text-slate-400 transition-all overflow-hidden"
        style={{ height: pullDistance > 0 || refreshing ? Math.max(pullDistance, refreshing ? 40 : 0) : 0 }}
      >
        {refreshing ? (
          <span className="animate-spin material-symbols-outlined text-primary text-base">refresh</span>
        ) : pullDistance >= threshold ? (
          '释放刷新'
        ) : pullDistance > 0 ? (
          '下拉刷新'
        ) : null}
      </div>
      {children}
    </div>
  )
}
