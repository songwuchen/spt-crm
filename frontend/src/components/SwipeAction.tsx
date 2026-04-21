import { useRef, useState, type ReactNode } from 'react'

interface SwipeActionProps {
  children: ReactNode
  actions?: { label: string; color: string; onClick: () => void }[]
  onLongPress?: () => void
}

/**
 * Mobile swipe-to-reveal actions component.
 * Swipe left to show action buttons. Long-press triggers callback.
 */
export default function SwipeAction({ children, actions = [], onLongPress }: SwipeActionProps) {
  const ref = useRef<HTMLDivElement>(null)
  const startXRef = useRef(0)
  const startYRef = useRef(0)
  const [offset, setOffset] = useState(0)
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const movedRef = useRef(false)
  const actionWidth = actions.length * 72

  const handleTouchStart = (e: React.TouchEvent) => {
    startXRef.current = e.touches[0].clientX
    startYRef.current = e.touches[0].clientY
    movedRef.current = false
    if (onLongPress) {
      longPressTimer.current = setTimeout(() => {
        if (!movedRef.current) {
          onLongPress()
          // Haptic feedback if available
          if (navigator.vibrate) navigator.vibrate(50)
        }
      }, 600)
    }
  }

  const handleTouchMove = (e: React.TouchEvent) => {
    const dx = e.touches[0].clientX - startXRef.current
    const dy = e.touches[0].clientY - startYRef.current
    if (Math.abs(dx) > 8 || Math.abs(dy) > 8) movedRef.current = true
    if (longPressTimer.current) clearTimeout(longPressTimer.current)
    if (actions.length === 0) return
    // Only respond to horizontal swipes
    if (Math.abs(dy) > Math.abs(dx)) return
    const newOffset = Math.min(0, Math.max(-actionWidth, dx + (offset < 0 ? -actionWidth : 0)))
    setOffset(newOffset)
  }

  const handleTouchEnd = () => {
    if (longPressTimer.current) clearTimeout(longPressTimer.current)
    if (actions.length === 0) return
    // Snap: if swiped more than half, stay open
    if (Math.abs(offset) > actionWidth / 2) {
      setOffset(-actionWidth)
    } else {
      setOffset(0)
    }
  }

  return (
    <div className="relative overflow-hidden rounded-xl">
      {/* Action buttons behind */}
      {actions.length > 0 && (
        <div className="absolute right-0 top-0 bottom-0 flex">
          {actions.map((action, i) => (
            <button
              key={i}
              onClick={() => { action.onClick(); setOffset(0) }}
              className="h-full flex items-center justify-center text-white text-sm font-bold"
              style={{ width: 72, backgroundColor: action.color }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
      {/* Main content */}
      <div
        ref={ref}
        className="relative bg-white transition-transform"
        style={{
          transform: `translateX(${offset}px)`,
          transition: movedRef.current ? 'none' : 'transform 0.2s ease-out',
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {children}
      </div>
    </div>
  )
}
