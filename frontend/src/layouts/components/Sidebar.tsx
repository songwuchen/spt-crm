import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'
import { useUiSettingsStore } from '@/stores/useUiSettingsStore'
import { menuGroups, PROTECTED_MENU_KEYS } from '@/config/menus'
import { t } from '@/locales'

function getSelectedKey(pathname: string): string {
  if (pathname.match(/^\/customers/)) return '/customers'
  if (pathname.match(/^\/customer-pool/)) return '/customer-pool'
  if (pathname.match(/^\/contacts/)) return '/contacts'
  if (pathname.match(/^\/leads/)) return '/leads'
  if (pathname.match(/^\/opportunities/)) return '/opportunities'
  if (pathname.match(/^\/solutions/)) return '/solutions'
  if (pathname.match(/^\/quotes/)) return '/quotes'
  if (pathname.match(/^\/contracts/)) return '/contracts'
  if (pathname.match(/^\/products/)) return '/products'
  if (pathname.match(/^\/orders/)) return '/orders'
  if (pathname.match(/^\/tenders/)) return '/tenders'
  if (pathname.match(/^\/follow-ups/)) return '/follow-ups'
  if (pathname.match(/^\/payments/)) return '/payments'
  if (pathname.match(/^\/commissions/)) return '/commissions'
  if (pathname.match(/^\/collection/)) return '/collection'
  if (pathname.match(/^\/guarantees/)) return '/guarantees'
  if (pathname.match(/^\/equipment-profile/)) return '/equipment-profile'
  if (pathname.match(/^\/service-tickets/)) return '/service-tickets'
  if (pathname.match(/^\/measurements/)) return '/measurements'
  if (pathname.match(/^\/sales-targets/)) return '/sales-targets'
  if (pathname.match(/^\/analytics/)) return '/analytics'
  if (pathname.match(/^\/calendar/)) return '/calendar'
  if (pathname.match(/^\/change-requests/)) return '/change-requests'
  if (pathname.match(/^\/milestones/)) return '/milestones'
  if (pathname.match(/^\/tasks/)) return '/tasks'
  if (pathname.match(/^\/approvals/)) return '/approvals'
  if (pathname.match(/^\/ai-center/)) return '/ai-center'
  if (pathname.match(/^\/admin\/departments/)) return '/admin/departments'
  if (pathname.match(/^\/admin\/users/)) return '/admin/users'
  if (pathname.match(/^\/admin\/roles/)) return '/admin/roles'
  if (pathname.match(/^\/admin\/audit/)) return '/admin/audit'
  if (pathname.match(/^\/admin\/settings/)) return '/admin/settings'
  if (pathname.match(/^\/admin\/api-docs/)) return '/admin/api-docs'
  if (pathname.match(/^\/admin\/openapi/)) return '/admin/openapi'
  if (pathname.match(/^\/admin\/system-health/)) return '/admin/system-health'
  if (pathname.match(/^\/admin\/dingtalk/)) return '/admin/dingtalk'
  if (pathname.match(/^\/admin\/data-manage/)) return '/admin/data-manage'
  return '/'
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const systemName = useUiSettingsStore((s) => s.systemName)
  const menuAliases = useUiSettingsStore((s) => s.menuAliases)
  const hiddenMenus = useUiSettingsStore((s) => s.hiddenMenus)
  const selectedKey = getSelectedKey(location.pathname)

  const hiddenSet = new Set(hiddenMenus)
  const brandName = systemName || 'SPT-CRM'

  return (
    <div className="sidebar-root">
      {/* Logo */}
      <div className="sidebar-logo">
        <img src="/logo.png" alt={brandName} className="sidebar-logo-icon" />
        <span className="sidebar-logo-text">{brandName}</span>
      </div>

      {/* Menu Groups */}
      <div className="sidebar-menu">
        {menuGroups.map((group) => {
          // 整组被隐藏 → 跳过
          if (hiddenSet.has(group.key)) return null
          const visibleItems = group.items.filter((item) => {
            if (!item.permission || hasPermission(item.permission)) {
              // 系统配置入口永不隐藏，避免管理员锁死
              return !hiddenSet.has(item.key) || PROTECTED_MENU_KEYS.includes(item.key)
            }
            return false
          })
          if (visibleItems.length === 0) return null
          return (
            <div key={group.key} className="sidebar-group">
              <div className="sidebar-group-title">{menuAliases[group.key] || t(group.titleKey)}</div>
              <nav className="sidebar-group-nav">
                {visibleItems.map((item) => {
                  const isActive = selectedKey === item.key
                  return (
                    <button
                      key={item.key}
                      onClick={() => navigate(item.key)}
                      className={`sidebar-item ${isActive ? 'sidebar-item--active' : ''}`}
                    >
                      <span className="material-symbols-outlined sidebar-item-icon">{item.icon}</span>
                      <span className="sidebar-item-label">{menuAliases[item.key] || t(item.labelKey)}</span>
                    </button>
                  )
                })}
              </nav>
            </div>
          )
        })}
      </div>

      {/* AI Status Panel */}
      <div className="sidebar-footer">
        <div className="sidebar-ai-panel">
          <div className="sidebar-ai-header">
            <span className="material-symbols-outlined sidebar-ai-icon">insights</span>
            <span className="sidebar-ai-title">AI 智能监控</span>
          </div>
          <p className="sidebar-ai-desc">
            引擎就绪，正在追踪 <span className="sidebar-ai-highlight">所有商机</span> 的智能建议。
          </p>
        </div>
      </div>

      <style>{`
        .sidebar-root {
          height: 100%;
          display: flex;
          flex-direction: column;
          background: #ffffff;
          border-right: 1px solid #e2e8f0;
          overflow: hidden;
        }
        .dark .sidebar-root {
          background: #0f172a;
          border-right-color: #1e293b;
        }

        /* ── Logo ── */
        .sidebar-logo {
          height: 64px;
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 0 20px;
          border-bottom: 1px solid #e2e8f0;
          flex-shrink: 0;
        }
        .dark .sidebar-logo {
          border-bottom-color: #1e293b;
        }
        .sidebar-logo-icon {
          width: 34px;
          height: 34px;
          border-radius: 9px;
          object-fit: cover;
          display: block;
          flex-shrink: 0;
          box-shadow: 0 2px 8px rgba(15,23,42,0.12);
        }
        .sidebar-logo-text {
          font-size: 15px;
          font-weight: 800;
          color: #0f172a;
          letter-spacing: -0.025em;
        }
        .dark .sidebar-logo-text {
          color: #e2e8f0;
        }

        /* ── Menu ── */
        .sidebar-menu {
          flex: 1;
          min-height: 0;
          padding: 16px 12px;
          display: flex;
          flex-direction: column;
          gap: 24px;
          overflow-y: auto;
        }
        .sidebar-group-title {
          padding: 0 12px;
          margin-bottom: 8px;
          font-size: 10px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: #94a3b8;
        }
        .dark .sidebar-group-title {
          color: #64748b;
        }
        .sidebar-group-nav {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        /* ── Menu Item ── */
        .sidebar-item {
          width: 100%;
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 12px;
          border-radius: 10px;
          border: none;
          background: transparent;
          cursor: pointer;
          transition: all 0.15s ease;
          font-family: inherit;
        }
        .sidebar-item-icon {
          font-size: 20px !important;
          line-height: 1;
        }
        .sidebar-item-label {
          font-size: 14px;
          font-weight: 500;
        }

        /* Default state */
        .sidebar-item:not(.sidebar-item--active) {
          color: #475569;
        }
        .dark .sidebar-item:not(.sidebar-item--active) {
          color: #94a3b8;
        }
        .sidebar-item:not(.sidebar-item--active):hover {
          background: #f1f5f9;
          color: #0f172a;
        }
        .dark .sidebar-item:not(.sidebar-item--active):hover {
          background: #1e293b;
          color: #e2e8f0;
        }

        /* Active state */
        .sidebar-item--active {
          background: #137fec;
          color: #ffffff;
          box-shadow: 0 2px 8px rgba(19,127,236,0.3);
        }
        .sidebar-item--active .sidebar-item-label {
          font-weight: 600;
        }

        /* ── AI Panel ── */
        .sidebar-footer {
          padding: 12px;
          flex-shrink: 0;
        }
        .sidebar-ai-panel {
          background: #f0f7ff;
          border-radius: 12px;
          border: 1px solid #dbeafe;
          padding: 16px;
        }
        .dark .sidebar-ai-panel {
          background: #1e293b;
          border-color: #334155;
        }
        .sidebar-ai-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }
        .sidebar-ai-icon {
          font-size: 18px !important;
          color: #137fec;
        }
        .sidebar-ai-title {
          font-size: 11px;
          font-weight: 700;
          color: #334155;
          letter-spacing: 0.025em;
        }
        .dark .sidebar-ai-title {
          color: #94a3b8;
        }
        .sidebar-ai-desc {
          font-size: 12px;
          color: #64748b;
          line-height: 1.5;
          margin: 0;
        }
        .sidebar-ai-highlight {
          color: #137fec;
          font-weight: 600;
        }
      `}</style>
    </div>
  )
}
