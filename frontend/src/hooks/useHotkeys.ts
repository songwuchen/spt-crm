import { useEffect } from 'react'
import { isImeComposing } from '@/utils/ime'

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
      // 中文输入法组字中：绝不能 preventDefault，否则候选框 Esc/选词会失效
      if (isImeComposing(e)) return

      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      const isInput = !!(
        tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
        || target?.isContentEditable
        || target?.closest?.('.ant-select-dropdown, .ant-picker-dropdown, .ant-mentions')
      )

      const parts: string[] = []
      if (e.ctrlKey || e.metaKey) parts.push('ctrl')
      if (e.shiftKey) parts.push('shift')
      if (e.altKey) parts.push('alt')
      parts.push((e.key || '').toLowerCase())
      const combo = parts.join('+')

      const fn = hotkeys[combo]
      if (!fn) return

      // Esc：输入框内留给 IME / 控件自身（Ant Design Modal 也会处理）
      if (combo === 'escape' && isInput) return
      // 其它快捷键：输入框内不触发
      if (combo !== 'escape' && isInput) return

      e.preventDefault()
      e.stopPropagation()
      fn()
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [hotkeys])
}
