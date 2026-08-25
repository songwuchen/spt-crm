import { useAuthStore } from '@/stores/useAuthStore'
import NoPermission from '@/pages/NoPermission'
import { useWorkflowFormTemplateCodes } from '@/hooks/useWorkflowFormTemplateCodes'
import { formTemplateCodeForRoute } from '@/config/formModuleRoutes'
import { useLocation } from 'react-router-dom'

interface Props {
  /** 单个权限，或任一命中即可（如方案管理兼容 solution:view / form_data:view） */
  permission: string | string[]
  /** 低代码模块：参与过该模板流程的用户也可进入（不必有 form_data:view） */
  formTemplateCode?: string
  children: React.ReactNode
}

export default function PermissionGuard({ permission, formTemplateCode, children }: Props) {
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const location = useLocation()
  const { codes } = useWorkflowFormTemplateCodes()
  const tplCode = formTemplateCode ?? formTemplateCodeForRoute(location.pathname)

  const permOk = Array.isArray(permission)
    ? permission.some((p) => hasPermission(p))
    : hasPermission(permission)
  const wfOk = !!(tplCode && codes.has(tplCode))

  if (permOk || wfOk) {
    return <>{children}</>
  }
  return <NoPermission />
}
