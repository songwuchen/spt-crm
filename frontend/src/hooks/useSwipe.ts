import { useRef, useCallback } from 'react'

interface SwipeHandlers {
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
  onSwipeUp?: () => void
  onSwipeDown?: () => void
}

export function useSwipe(handlers: SwipeHandlers, threshold = 50) {
  const startRef = useRef<{ x: number; y: number } | null>(null)

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    startRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
  }, [])

  const onTouchEnd = useCallback((e: React.TouchEvent) => {
    if (!startRef.current) return
    const dx = e.changedTouches[0].clientX - startRef.current.x
    const dy = e.changedTouches[0].clientY - startRef.current.y
    startRef.current = null

    if (Math.abs(dx) > Math.abs(dy)) {
      if (dx > threshold) handlers.onSwipeRight?.()
      else if (dx < -threshold) handlers.onSwipeLeft?.()
    } else {
      if (dy > threshold) handlers.onSwipeDown?.()
      else if (dy < -threshold) handlers.onSwipeUp?.()
    }
  }, [handlers, threshold])

  return { onTouchStart, onTouchEnd }
}
