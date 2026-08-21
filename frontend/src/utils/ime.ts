/** 是否处于中文等 IME 组字中（此时勿拦截快捷键 / Enter / Esc）。 */
export function isImeComposing(
  e: KeyboardEvent | { isComposing?: boolean; keyCode?: number; key?: string; nativeEvent?: KeyboardEvent },
): boolean {
  if (e.isComposing) return true
  const ne = 'nativeEvent' in e && e.nativeEvent ? e.nativeEvent : null
  if (ne?.isComposing) return true
  // Chromium / 多数 Windows IME 组字中的 keydown
  if (e.keyCode === 229 || ne?.keyCode === 229) return true
  if (e.key === 'Process' || ne?.key === 'Process') return true
  return false
}
