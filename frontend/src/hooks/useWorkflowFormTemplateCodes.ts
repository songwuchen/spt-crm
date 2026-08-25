import { useEffect, useState } from 'react'
import { lowcodeApi } from '@/api/lowcode'
import { useAuthStore } from '@/stores/useAuthStore'

let cachedCodes: Set<string> | null = null
let inflight: Promise<Set<string>> | null = null

function fetchCodes(): Promise<Set<string>> {
  if (cachedCodes) return Promise.resolve(cachedCodes)
  if (inflight) return inflight
  inflight = lowcodeApi
    .getWorkflowVisibleFormCodes()
    .then((res) => {
      cachedCodes = new Set(res.data?.codes ?? [])
      return cachedCodes
    })
    .catch(() => new Set<string>())
    .finally(() => {
      inflight = null
    })
  return inflight
}

/** 清除缓存（登出时调用） */
export function clearWorkflowFormTemplateCodesCache() {
  cachedCodes = null
  inflight = null
}

/** 用户参与过流程的表单模板 code；有 form_data:view 时不请求。 */
export function useWorkflowFormTemplateCodes() {
  const token = useAuthStore((s) => s.token)
  const hasFormView = useAuthStore((s) => s.hasPermission('form_data:view'))
  const [codes, setCodes] = useState<Set<string>>(() => cachedCodes ?? new Set())
  const [loaded, setLoaded] = useState(Boolean(cachedCodes) || hasFormView)

  useEffect(() => {
    if (hasFormView || !token) {
      setLoaded(true)
      return
    }
    let cancelled = false
    void fetchCodes().then((set) => {
      if (!cancelled) {
        setCodes(set)
        setLoaded(true)
      }
    })
    return () => {
      cancelled = true
    }
  }, [token, hasFormView])

  return { codes, loaded, hasFormView }
}
