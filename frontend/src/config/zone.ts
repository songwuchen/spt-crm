// Host-based UI zoning.
//
// All three production domains are served by the SAME frontend container on the
// SAME port (see nginx.prod.conf). The domain decides which UI a visitor lands in:
//   - wm.fourier.net.cn          → 完整 Web 端
//   - link.fourier.net.cn        → 移动端
//   - wm-platform.fourier.net.cn → 平台管理端
//
// Unknown hosts (localhost / IP / preview): infer from path prefix so that
// visiting /m/... on the same Vite server stays in the mobile zone (e.g.
// notification jumps must not land on desktop routes).

export type Zone = 'web' | 'mobile' | 'platform'

const HOST_ZONE: Record<string, Zone> = {
  'link.fourier.net.cn': 'mobile',
  'wm-platform.fourier.net.cn': 'platform',
  'wm.fourier.net.cn': 'web',
}

export function currentZone(): Zone {
  if (typeof window === 'undefined') return 'web'
  const byHost = HOST_ZONE[window.location.hostname]
  if (byHost) return byHost
  const path = window.location.pathname
  if (path === '/m' || path.startsWith('/m/')) return 'mobile'
  if (path === '/platform' || path.startsWith('/platform/')) return 'platform'
  return 'web'
}

// Default landing route per zone (used for the root path "/" and post-login).
export const ZONE_HOME: Record<Zone, string> = {
  web: '/',
  mobile: '/m',
  platform: '/platform/tenants',
}
