import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'

interface MenuItem {
  key: string
  icon: string
  label: string
  permission?: string
}

const menuGroups: { title: string; items: MenuItem[] }[] = [
  {
    title: '业务管理',
    items: [
      { key: '/', icon: 'dashboard', label: '工作台' },
      { key: '/customers', icon: 'business', label: '客户管理', permission: 'customer:view' },
      { key: '/leads', icon: 'trending_up', label: '线索管理', permission: 'lead:view' },
      { key: '/opportunities', icon: 'rocket_launch', label: '商机管理', permission: 'project:view' },
      { key: '/follow-ups', icon: 'contact_phone', label: '跟进记录', permission: 'customer:view' },
      { key: '/payments', icon: 'account_balance', label: '回款管理', permission: 'payment:view' },
      { key: '/service-tickets', icon: 'confirmation_number', label: '售后工单', permission: 'service:view' },
      { key: '/analytics', icon: 'analytics', label: '销售分析', permission: 'project:view' },
      { key: '/approvals', icon: 'task_alt', label: '审批中心' },
      { key: '/ai-center', icon: 'smart_toy', label: 'AI 任务中心', permission: 'project:view' },
    ],
  },
  {
    title: '系统设置',
    items: [
      { key: '/admin/departments', icon: 'account_tree', label: '部门管理', permission: 'dept:view' },
      { key: '/admin/users', icon: 'group', label: '用户管理', permission: 'user:view' },
      { key: '/admin/roles', icon: 'admin_panel_settings', label: '角色权限', permission: 'role:view' },
      { key: '/admin/audit', icon: 'history', label: '审计日志', permission: 'audit:view' },
      { key: '/admin/settings', icon: 'settings', label: '系统配置', permission: 'role:manage' },
    ],
  },
]

function getSelectedKey(pathname: string): string {
  if (pathname.match(/^\/customers/)) return '/customers'
  if (pathname.match(/^\/leads/)) return '/leads'
  if (pathname.match(/^\/opportunities/)) return '/opportunities'
  if (pathname.match(/^\/follow-ups/)) return '/follow-ups'
  if (pathname.match(/^\/payments/)) return '/payments'
  if (pathname.match(/^\/service-tickets/)) return '/service-tickets'
  if (pathname.match(/^\/analytics/)) return '/analytics'
  if (pathname.match(/^\/approvals/)) return '/approvals'
  if (pathname.match(/^\/ai-center/)) return '/ai-center'
  if (pathname.match(/^\/admin\/departments/)) return '/admin/departments'
  if (pathname.match(/^\/admin\/users/)) return '/admin/users'
  if (pathname.match(/^\/admin\/roles/)) return '/admin/roles'
  if (pathname.match(/^\/admin\/audit/)) return '/admin/audit'
  if (pathname.match(/^\/admin\/settings/)) return '/admin/settings'
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
            <div key={group.title} className="sidebar-group">
              <div className="sidebar-group-title">{group.title}</div>
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
                      <span className="sidebar-item-label">{item.label}</span>
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
          overflow-y: auto;
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

        /* ── Menu ── */
        .sidebar-menu {
          flex: 1;
          padding: 16px 12px;
          display: flex;
          flex-direction: column;
          gap: 24px;
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
        .sidebar-item:not(.sidebar-item--active):hover {
          background: #f1f5f9;
          color: #0f172a;
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
