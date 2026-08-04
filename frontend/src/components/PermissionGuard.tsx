import { useAuthStore } from '@/stores/useAuthStore'
import NoPermission from '@/pages/NoPermission'

interface Props {
  /** 单个权限，或任一命中即可（如方案管理兼容 solution:view / form_data:view） */
  permission: string | string[]
  children: React.ReactNode
}

export default function PermissionGuard({ permission, children }: Props) {
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const ok = Array.isArray(permission)
    ? permission.some((p) => hasPermission(p))
    : hasPermission(permission)
  if (!ok) {
    return <NoPermission />
  }
  return <>{children}</>
}
