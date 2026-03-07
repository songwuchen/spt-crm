import { useEffect, useRef, useCallback } from 'react'

const STORAGE_PREFIX = 'spt_draft_'

/**
 * Auto-save form values to localStorage with debounce.
 * Usage:
 *   const { restoreDraft, clearDraft } = useAutoSave('customer_form', form)
 *   // Call restoreDraft() in useEffect to load saved draft
 *   // Call clearDraft() after successful submit
 */
export function useAutoSave(
  key: string,
  form: { getFieldsValue: () => Record<string, unknown>; setFieldsValue: (v: Record<string, unknown>) => void },
  debounceMs = 2000,
) {
  const storageKey = STORAGE_PREFIX + key
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-save on form changes
  useEffect(() => {
    const save = () => {
      try {
        const values = form.getFieldsValue()
        // Filter out undefined/null fields and dayjs objects (serialize as ISO string)
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
    }

    // Use MutationObserver-free approach: poll form values
    const interval = setInterval(save, debounceMs)
    return () => clearInterval(interval)
  }, [form, storageKey, debounceMs])

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

  return { restoreDraft, clearDraft }
}
