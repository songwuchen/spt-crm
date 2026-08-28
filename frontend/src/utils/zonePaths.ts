import { currentZone, type Zone } from '@/config/zone'

/** PC 路由 → 移动端 /m 前缀路由（无对应则返回原路径） */
const DESKTOP_TO_MOBILE: Record<string, string> = {
  '/': '/m',
  '/customers': '/m/customers',
  '/customer-pool': '/m/customer-pool',
  '/contacts': '/m/contacts',
  '/leads': '/m/leads',
  '/lead-reactivations': '/m/lead-reactivations',
  '/opportunities': '/m/opportunities',
  '/opportunities/kanban': '/m/kanban',
  '/contracts': '/m/contracts',
  '/contracts/dashboard': '/m/contracts/dashboard',
  '/contract-reviews': '/m/contract-reviews',
  '/tech-agreement-reviews': '/m/tech-agreement-reviews',
  '/payments': '/m/payments',
  '/commissions': '/m/commissions',
  '/collection': '/m/collection',
  '/guarantees': '/m/guarantees',
  '/service-tickets': '/m/service-tickets',
  '/follow-ups': '/m/follow-ups',
  '/products': '/m/products',
  '/orders': '/m/orders',
  '/tenders': '/m/tenders',
  '/tasks': '/m/tasks',
  '/calendar': '/m/calendar',
  '/analytics': '/m/analytics',
  '/sales-targets': '/m/sales-targets',
  '/reports/product': '/m/reports/product',
  '/reports/customer-lifecycle': '/m/reports/customer-lifecycle',
  '/reports/team-performance': '/m/reports/team-performance',
  '/approvals': '/m/approvals',
  '/notifications': '/m/notifications',
  '/solutions': '/m/solutions',
  '/lowcode/forms': '/m/form-modules',
  '/lowcode/approvals': '/m/lowcode/approvals',
  '/change-requests': '/m/change-requests',
  '/milestones': '/m/milestones',
  '/equipment-profile': '/m/equipment-profile',
  '/measurements': '/m/measurements',
  '/ai-center': '/m/ai-center',
  '/knowledge-base': '/m/knowledge-base',
}

/** 低代码业务模块列表页（与 workflowBizPath / formModuleRoutes 一致） */
const FORM_MODULE_BASES = [
  '/drawing-requisitions',
  '/install-drawing-notices',
  '/presale-service-notices',
  '/contract-drawing-maps',
  '/application-fields',
  '/application-materials',
  '/material-names',
  '/department-codes',
  '/salesperson-region-map',
  '/quotes',
  '/pricing-checklists',
  '/research-coop-cards',
  '/tech-agreement-feedbacks',
  '/contract-outsource-early',
  '/biz-bonus-transfer',
  '/biz-bonus-biz-initiate',
  '/commission-database',
  '/prod-card-supplements',
  '/invoice-applications',
  '/shipment-notices',
  '/xunhan-contract-reviews',
  '/payment-registrations',
  '/contract-shipment-loans',
  '/contract-shipment-loans/shipment-dashboard',
  '/cs-service-requests',
  '/cs-product-replaces',
  '/cs-product-returns',
  '/cs-loan-slips',
  '/cs-drawing-requests',
  '/cs-service-delays',
  '/cs-correspondences',
] as const

for (const base of FORM_MODULE_BASES) {
  DESKTOP_TO_MOBILE[base] = `/m${base}`
}

function splitPathQueryHash(raw: string): { path: string; suffix: string } {
  const hashIdx = raw.indexOf('#')
  const beforeHash = hashIdx >= 0 ? raw.slice(0, hashIdx) : raw
  const hash = hashIdx >= 0 ? raw.slice(hashIdx) : ''
  const qIdx = beforeHash.indexOf('?')
  const path = qIdx >= 0 ? beforeHash.slice(0, qIdx) : beforeHash
  const suffix = (qIdx >= 0 ? beforeHash.slice(qIdx) : '') + hash
  return { path, suffix }
}

/** 将 PC 深链转为当前 zone 可用路径（mobile 域名下自动加 /m 前缀） */
export function toZonePath(rawPath: string, zone?: Zone): string {
  const z = zone ?? currentZone()
  if (z !== 'mobile') return rawPath
  const { path, suffix } = splitPathQueryHash(rawPath)
  if (!path || path === '/m' || path.startsWith('/m/')) return rawPath

  const exact = DESKTOP_TO_MOBILE[path]
  if (exact) return `${exact}${suffix}`

  for (const [desk, mob] of Object.entries(DESKTOP_TO_MOBILE)) {
    if (desk !== '/' && path.startsWith(`${desk}/`)) {
      return `${mob}${path.slice(desk.length)}${suffix}`
    }
  }

  for (const base of FORM_MODULE_BASES) {
    if (path === base || path.startsWith(`${base}/`)) {
      return `/m${path}${suffix}`
    }
  }

  // 通用：/foo/bar → /m/foo/bar
  return `/m${path}${suffix}`
}

/** mobile 域名访问 PC 根路由时的重定向目标（保留 query） */
export function mobileZoneRedirectTarget(): string {
  if (typeof window === 'undefined') return '/m'
  return toZonePath(window.location.pathname + window.location.search + window.location.hash, 'mobile')
}
