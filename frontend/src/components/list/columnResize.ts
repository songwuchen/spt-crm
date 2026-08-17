/** 列宽松手回调（按 colKey）。不在 effect cleanup 里 delete，避免 React StrictMode 误删。 */
const stopHandlers = new Map<string, (width: number) => void>()

export function registerColumnResizeStop(colKey: string, fn: (width: number) => void) {
  stopHandlers.set(colKey, fn)
}

export function getColumnResizeStop(colKey: string) {
  return stopHandlers.get(colKey)
}

export function clampColWidth(w: number) {
  return Math.min(960, Math.max(64, Math.round(w)))
}
