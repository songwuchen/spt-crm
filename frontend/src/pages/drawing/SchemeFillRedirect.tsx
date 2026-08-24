/**
 * 旧版「方案管理」合并填报已下线，按 scheme_type 分流到独立表单。
 */
import { Navigate, useLocation } from 'react-router-dom'

function mapPrefill(prefill: Record<string, unknown> | undefined, target: 'install' | 'requisition') {
  const next = { ...(prefill || {}) }
  delete next.scheme_type
  if (target === 'install') {
    if (next.related_project && !next.project_no) {
      next.project_no = next.related_project
    }
    delete next.related_project
  }
  return Object.keys(next).length ? { prefillFormData: next } : undefined
}

export default function SchemeFillRedirect() {
  const location = useLocation()
  const prefill = (location.state as { prefillFormData?: Record<string, unknown> } | null)?.prefillFormData
  const qs = new URLSearchParams(location.search)
  const schemeType = String(prefill?.scheme_type || qs.get('scheme_type') || '').trim()

  if (schemeType === 'install') {
    return (
      <Navigate
        to="/install-drawing-notices/fill"
        replace
        state={mapPrefill(prefill, 'install')}
      />
    )
  }

  return (
    <Navigate
      to="/drawing-requisitions/fill"
      replace
      state={mapPrefill(prefill, 'requisition')}
    />
  )
}
