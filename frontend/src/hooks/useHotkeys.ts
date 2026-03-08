import { useEffect } from 'react'

interface HotkeyMap {
  [key: string]: () => void
}

/**
 * Register global keyboard shortcuts.
 * Keys format: "ctrl+k", "ctrl+n", "escape"
 */
export function useHotkeys(hotkeys: HotkeyMap) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable

      const parts: string[] = []
      if (e.ctrlKey || e.metaKey) parts.push('ctrl')
      if (e.shiftKey) parts.push('shift')
      if (e.altKey) parts.push('alt')
      parts.push(e.key.toLowerCase())
      const combo = parts.join('+')

      const fn = hotkeys[combo]
      if (fn) {
        // Allow Escape in inputs, block other shortcuts in inputs
        if (combo !== 'escape' && isInput) return
        e.preventDefault()
        e.stopPropagation()
        fn()
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [hotkeys])
}
