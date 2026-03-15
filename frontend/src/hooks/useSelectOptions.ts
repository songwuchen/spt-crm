import { useRemoteSelect } from './useRemoteSelect'
import { userApi } from '@/api/user'
import { customerApi } from '@/api/customer'

/**
 * Pre-configured remote select for user selection.
 * Replaces the duplicated useRemoteSelect(userApi.list) pattern.
 */
export function useUserSelect() {
  return useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({
      label: u.real_name || u.username,
      value: u.id,
    }))
  })
}

/**
 * Pre-configured remote select for customer selection.
 * Replaces the duplicated useRemoteSelect(customerApi.list) pattern.
 */
export function useCustomerSelect() {
  return useRemoteSelect(async (kw) => {
    const r = await customerApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((c: any) => ({
      label: c.name,
      value: c.id,
    }))
  })
}
