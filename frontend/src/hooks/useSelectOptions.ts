import { useRemoteSelect } from './useRemoteSelect'
import { userApi } from '@/api/user'
import { customerApi } from '@/api/customer'
import { leadApi } from '@/api/lead'
import { projectApi } from '@/api/project'
import { serviceTicketApi } from '@/api/serviceTicket'

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

/** Remote select for leads (线索) — used when associating a follow-up with a lead. */
export function useLeadSelect() {
  return useRemoteSelect(async (kw) => {
    const r = await leadApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((l: any) => ({
      label: l.title || l.company_name || l.lead_code || l.id,
      value: l.id,
    }))
  })
}

/** Remote select for opportunity projects (商机). */
export function useProjectSelect() {
  return useRemoteSelect(async (kw) => {
    const r = await projectApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((p: any) => ({
      label: p.name || p.project_code || p.id,
      value: p.id,
    }))
  })
}

/** Remote select for service tickets (工单). */
export function useServiceTicketSelect() {
  return useRemoteSelect(async (kw) => {
    const r = await serviceTicketApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((t: any) => ({
      label: t.description ? `${t.ticket_no} · ${t.description}` : t.ticket_no || t.id,
      value: t.id,
    }))
  })
}

/** Pick the right entity select for a follow-up biz_type. */
export function useBizObjectSelects() {
  const customer = useCustomerSelect()
  const lead = useLeadSelect()
  const project = useProjectSelect()
  const service_ticket = useServiceTicketSelect()
  const byType: Record<string, ReturnType<typeof useCustomerSelect>> = {
    customer, lead, project, service_ticket,
  }
  return (bizType: string) => byType[bizType] || customer
}
