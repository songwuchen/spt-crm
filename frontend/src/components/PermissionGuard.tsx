import { useAuthStore } from '@/stores/useAuthStore'
import NoPermission from '@/pages/NoPermission'

interface Props {
  permission: string
  children: React.ReactNode
}

export default function PermissionGuard({ permission, children }: Props) {
  const hasPermission = useAuthStore((s) => s.hasPermission)
  if (!hasPermission(permission)) {
    return <NoPermission />
  }
  return <>{children}</>
}
