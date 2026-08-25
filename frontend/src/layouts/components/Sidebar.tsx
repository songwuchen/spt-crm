import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'
import { useUiSettingsStore } from '@/stores/useUiSettingsStore'
import { menuGroups, PROTECTED_MENU_KEYS, flattenMenuItems, type MenuItem } from '@/config/menus'
import { t } from '@/locales'
import { useApprovalPendingCount } from '@/hooks/useApprovalPendingCount'
import { useNotificationUnreadCount } from '@/hooks/useNotificationUnreadCount'
import { useWorkflowFormTemplateCodes } from '@/hooks/useWorkflowFormTemplateCodes'
import { formTemplateCodeForRoute } from '@/config/formModuleRoutes'

import Icon from '@/components/Icon'

/** 侧栏高亮：按菜单项 key 最长前缀匹配；无匹配时不高亮（勿回落到工作台）。 */
function getSelectedKey(pathname: string): string {
  const keys = flattenMenuItems().map((i) => i.key)
  let best = ''
  let bestLen = 0
  for (const key of keys) {
    if (key === '/') {
      if (pathname === '/' || pathname === '') return '/'
      continue
    }
    if (pathname === key || pathname.startsWith(key + '/')) {
      if (key.length > bestLen) {
        best = key
        bestLen = key.length
      }
    }
  }
  return best
}

function permOk(
  item: MenuItem,
  hasPermission: (p: string) => boolean,
  wfFormCodes: Set<string>,
): boolean {
  const tpl = formTemplateCodeForRoute(item.key)
  if (tpl && wfFormCodes.has(tpl)) return true
  if (!item.permission) return true
  if (Array.isArray(item.permission)) return item.permission.some((p) => hasPermission(p))
  return hasPermission(item.permission)
}

function isItemVisible(
  item: MenuItem,
  hasPermission: (p: string) => boolean,
  hiddenSet: Set<string>,
  wfFormCodes: Set<string>,
): boolean {
  if (hiddenSet.has(item.key) && !PROTECTED_MENU_KEYS.includes(item.key)) return false
  if (item.children?.length) {
    return item.children.some((c) => isItemVisible(c, hasPermission, hiddenSet, wfFormCodes))
  }
  return permOk(item, hasPermission, wfFormCodes)
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const { codes: wfFormCodes } = useWorkflowFormTemplateCodes()
  const systemName = useUiSettingsStore((s) => s.systemName)
  const menuAliases = useUiSettingsStore((s) => s.menuAliases)
  const hiddenMenus = useUiSettingsStore((s) => s.hiddenMenus)
  const selectedKey = getSelectedKey(location.pathname)
  const approvalPendingCount = useApprovalPendingCount(60_000, location.pathname)
  const notificationUnreadCount = useNotificationUnreadCount(60_000, location.pathname)

  const hiddenSet = new Set(hiddenMenus)
  const brandName = systemName || 'SPT-CRM'

  const [openSubs, setOpenSubs] = useState<Record<string, boolean>>({})

  // 当前路由落在某子菜单下时自动展开
  useEffect(() => {
    for (const g of menuGroups) {
      for (const item of g.items) {
        if (!item.children?.length) continue
        if (item.children.some((c) => c.key === selectedKey)) {
          setOpenSubs((prev) => (prev[item.key] ? prev : { ...prev, [item.key]: true }))
        }
      }
    }
  }, [selectedKey])

  const toggleSub = (key: string) =>
    setOpenSubs((prev) => ({ ...prev, [key]: !prev[key] }))

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
          if (hiddenSet.has(group.key)) return null
          const visibleItems = group.items.filter((item) => isItemVisible(item, hasPermission, hiddenSet, wfFormCodes))
          if (visibleItems.length === 0) return null
          return (
            <div key={group.key} className="sidebar-group">
              <div className="sidebar-group-title">{menuAliases[group.key] || t(group.titleKey)}</div>
              <nav className="sidebar-group-nav">
                {visibleItems.map((item) => {
                  if (item.children?.length) {
                    const kids = item.children.filter((c) => isItemVisible(c, hasPermission, hiddenSet, wfFormCodes))
                    if (kids.length === 0) return null
                    const opened = !!openSubs[item.key]
                    const childActive = kids.some((c) => c.key === selectedKey)
                    return (
                      <div key={item.key} className="sidebar-sub">
                        <button
                          type="button"
                          onClick={() => toggleSub(item.key)}
                          className={`sidebar-item sidebar-item--parent ${childActive ? 'sidebar-item--parent-active' : ''}`}
                        >
                          <Icon name={item.icon} className="sidebar-item-icon" />
                          <span className="sidebar-item-label">{menuAliases[item.key] || t(item.labelKey)}</span>
                          <Icon
                            name={opened ? 'expand_less' : 'expand_more'}
                            className="sidebar-item-chevron"
                          />
                        </button>
                        {opened && (
                          <div className="sidebar-sub-nav">
                            {kids.map((child) => {
                              const isActive = selectedKey === child.key
                              return (
                                <button
                                  key={child.key}
                                  type="button"
                                  onClick={() => navigate(child.key)}
                                  className={`sidebar-item sidebar-item--child ${isActive ? 'sidebar-item--active' : ''}`}
                                >
                                  <Icon name={child.icon} className="sidebar-item-icon" />
                                  <span className="sidebar-item-label">{menuAliases[child.key] || t(child.labelKey)}</span>
                                </button>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  }

                  const isActive = selectedKey === item.key
                  const badge = item.key === '/approvals'
                    ? approvalPendingCount
                    : item.key === '/notifications'
                      ? notificationUnreadCount
                      : 0
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => navigate(item.key)}
                      className={`sidebar-item ${isActive ? 'sidebar-item--active' : ''}`}
                    >
                      <Icon name={item.icon} className="sidebar-item-icon" />
                      <span className="sidebar-item-label">{menuAliases[item.key] || t(item.labelKey)}</span>
                      {badge > 0 && (
                        <span
                          className="sidebar-item-badge"
                          aria-label={item.key === '/notifications' ? `${badge} 条未读` : `${badge} 条待办`}
                        >
                          {badge > 99 ? '99+' : badge}
                        </span>
                      )}
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
            <Icon name="insights" className="sidebar-ai-icon" />
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
        .sidebar-sub-nav {
          display: flex;
          flex-direction: column;
          gap: 2px;
          margin: 2px 0 6px 18px;
          padding: 4px 0 4px 10px;
          border-left: 2px solid #e2e8f0;
        }
        .dark .sidebar-sub-nav {
          border-left-color: #334155;
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
        .sidebar-item--child {
          padding: 8px 10px;
          gap: 10px;
        }
        .sidebar-item--child .sidebar-item-icon {
          font-size: 18px !important;
        }
        .sidebar-item--child .sidebar-item-label {
          font-size: 13px;
        }
        .sidebar-item-icon {
          font-size: 20px !important;
          line-height: 1;
        }
        .sidebar-item-label {
          font-size: 14px;
          font-weight: 500;
          flex: 1;
          text-align: left;
          min-width: 0;
        }
        .sidebar-item-chevron {
          font-size: 18px !important;
          opacity: 0.7;
          flex-shrink: 0;
        }
        .sidebar-item-badge {
          margin-left: auto;
          flex-shrink: 0;
          min-width: 18px;
          height: 18px;
          padding: 0 6px;
          border-radius: 999px;
          background: #ef4444;
          color: #ffffff;
          font-size: 11px;
          font-weight: 700;
          line-height: 18px;
          text-align: center;
          box-sizing: border-box;
        }
        .sidebar-item--active .sidebar-item-badge {
          background: rgba(255, 255, 255, 0.95);
          color: #137fec;
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
        .sidebar-item--parent-active:not(.sidebar-item--active) {
          color: #137fec;
          font-weight: 600;
        }
        .sidebar-item--parent-active .sidebar-item-label {
          font-weight: 600;
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
