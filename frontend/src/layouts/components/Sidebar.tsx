import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'
import { t } from '@/locales'

interface MenuItem {
  key: string
  icon: string
  labelKey: string
  permission?: string
}

const menuGroups: { titleKey: string; items: MenuItem[] }[] = [
  {
    titleKey: 'nav.businessGroup',
    items: [
      { key: '/', icon: 'dashboard', labelKey: 'nav.dashboard' },
      { key: '/customers', icon: 'business', labelKey: 'nav.customers', permission: 'customer:view' },
      { key: '/customer-pool', icon: 'waves', labelKey: 'nav.customerPool', permission: 'customer:view' },
      { key: '/contacts', icon: 'contacts', labelKey: 'nav.contacts', permission: 'contact:view' },
      { key: '/leads', icon: 'trending_up', labelKey: 'nav.leads', permission: 'lead:view' },
      { key: '/opportunities', icon: 'rocket_launch', labelKey: 'nav.opportunities', permission: 'project:view' },
      { key: '/products', icon: 'inventory_2', labelKey: 'nav.products', permission: 'product:view' },
      { key: '/follow-ups', icon: 'contact_phone', labelKey: 'nav.followUps', permission: 'customer:view' },
      { key: '/payments', icon: 'account_balance', labelKey: 'nav.payments', permission: 'payment:view' },
      { key: '/service-tickets', icon: 'confirmation_number', labelKey: 'nav.serviceTickets', permission: 'service:view' },
      { key: '/sales-targets', icon: 'flag', labelKey: 'nav.salesTargets', permission: 'project:view' },
      { key: '/analytics', icon: 'analytics', labelKey: 'nav.analytics', permission: 'project:view' },
      { key: '/calendar', icon: 'calendar_month', labelKey: 'nav.calendar' },
      { key: '/change-requests', icon: 'swap_horiz', labelKey: 'nav.changeRequests', permission: 'change:view' },
      { key: '/milestones', icon: 'flag_circle', labelKey: 'nav.milestones', permission: 'delivery:view' },
      { key: '/tasks', icon: 'checklist', labelKey: 'nav.tasks' },
      { key: '/approvals', icon: 'task_alt', labelKey: 'nav.approvals' },
      { key: '/ai-center', icon: 'smart_toy', labelKey: 'nav.aiCenter', permission: 'project:view' },
      { key: '/knowledge-base', icon: 'menu_book', labelKey: 'nav.knowledgeBase', permission: 'project:view' },
    ],
  },
  {
    titleKey: 'nav.systemGroup',
    items: [
      { key: '/admin/departments', icon: 'account_tree', labelKey: 'nav.departments', permission: 'dept:view' },
      { key: '/admin/users', icon: 'group', labelKey: 'nav.users', permission: 'user:view' },
      { key: '/admin/roles', icon: 'admin_panel_settings', labelKey: 'nav.roles', permission: 'role:view' },
      { key: '/admin/audit', icon: 'history', labelKey: 'nav.auditLog', permission: 'audit:view' },
      { key: '/admin/settings', icon: 'settings', labelKey: 'nav.settings', permission: 'role:manage' },
      { key: '/admin/api-docs', icon: 'api', labelKey: 'nav.apiDocs', permission: 'role:manage' },
      { key: '/admin/system-health', icon: 'monitor_heart', labelKey: 'nav.systemHealth', permission: 'role:manage' },
      { key: '/admin/dingtalk', icon: 'phonelink_ring', labelKey: 'nav.dingTalk', permission: 'role:manage' },
      { key: '/admin/data-manage', icon: 'delete_sweep', labelKey: 'nav.dataManage', permission: 'role:manage' },
    ],
  },
]

function getSelectedKey(pathname: string): string {
  if (pathname.match(/^\/customers/)) return '/customers'
  if (pathname.match(/^\/customer-pool/)) return '/customer-pool'
  if (pathname.match(/^\/contacts/)) return '/contacts'
  if (pathname.match(/^\/leads/)) return '/leads'
  if (pathname.match(/^\/opportunities/)) return '/opportunities'
  if (pathname.match(/^\/products/)) return '/products'
  if (pathname.match(/^\/follow-ups/)) return '/follow-ups'
  if (pathname.match(/^\/payments/)) return '/payments'
  if (pathname.match(/^\/service-tickets/)) return '/service-tickets'
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
  if (pathname.match(/^\/admin\/system-health/)) return '/admin/system-health'
  if (pathname.match(/^\/admin\/dingtalk/)) return '/admin/dingtalk'
  if (pathname.match(/^\/admin\/data-manage/)) return '/admin/data-manage'
  return '/'
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const selectedKey = getSelectedKey(location.pathname)

  return (
    <div className="sidebar-root">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <span className="material-symbols-outlined" style={{ fontSize: 20, color: '#fff' }}>factory</span>
        </div>
        <span className="sidebar-logo-text">Industrial AI-CRM</span>
      </div>

      {/* Menu Groups */}
      <div className="sidebar-menu">
        {menuGroups.map((group) => {
          const visibleItems = group.items.filter(
            (item) => !item.permission || hasPermission(item.permission)
          )
          if (visibleItems.length === 0) return null
          return (
            <div key={group.titleKey} className="sidebar-group">
              <div className="sidebar-group-title">{t(group.titleKey)}</div>
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
                      <span className="sidebar-item-label">{t(item.labelKey)}</span>
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
          background: #137fec;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 8px rgba(19,127,236,0.25);
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
