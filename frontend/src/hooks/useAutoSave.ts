import { useEffect, useRef, useCallback } from 'react'

const STORAGE_PREFIX = 'spt_draft_'

/**
 * Auto-save form values to localStorage with dirty-flag + debounce.
 * Usage:
 *   const { restoreDraft, clearDraft, markDirty } = useAutoSave('customer_form', form)
 *   // Call restoreDraft() in useEffect to load saved draft
 *   // Call clearDraft() after successful submit
 *   // markDirty() is returned for manual trigger; also call it from Form onValuesChange
 */
export function useAutoSave(
  key: string,
  form: { getFieldsValue: () => Record<string, unknown>; setFieldsValue: (v: Record<string, unknown>) => void },
  debounceMs = 2000,
) {
  const storageKey = STORAGE_PREFIX + key
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dirtyRef = useRef(false)

  const save = useCallback(() => {
    if (!dirtyRef.current) return
    dirtyRef.current = false
    try {
      const values = form.getFieldsValue()
      const cleaned: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(values)) {
        if (v === undefined || v === null) continue
        if (v && typeof v === 'object' && 'format' in v && typeof (v as any).format === 'function') {
          cleaned[k] = (v as any).toISOString()
        } else {
          cleaned[k] = v
        }
      }
      if (Object.keys(cleaned).length > 0) {
        localStorage.setItem(storageKey, JSON.stringify({ ts: Date.now(), data: cleaned }))
      }
    } catch { /* ignore storage errors */ }
  }, [form, storageKey])

  const markDirty = useCallback(() => {
    dirtyRef.current = true
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(save, debounceMs)
  }, [save, debounceMs])

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [])

  const restoreDraft = useCallback((): boolean => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return false
      const { ts, data } = JSON.parse(raw)
      // Only restore drafts less than 24 hours old
      if (Date.now() - ts > 24 * 60 * 60 * 1000) {
        localStorage.removeItem(storageKey)
        return false
      }
      form.setFieldsValue(data)
      return true
    } catch {
      return false
    }
  }, [storageKey, form])

  const clearDraft = useCallback(() => {
    localStorage.removeItem(storageKey)
  }, [storageKey])

  return { restoreDraft, clearDraft, markDirty }
}
