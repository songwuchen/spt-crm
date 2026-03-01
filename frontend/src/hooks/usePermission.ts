import { useAuthStore } from '@/stores/useAuthStore'

export function usePermission() {
  const hasPermission = useAuthStore((s) => s.hasPermission)
  return { hasPermission }
}
