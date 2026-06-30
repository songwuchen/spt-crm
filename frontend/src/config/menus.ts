// 菜单注册表 —— 侧边栏与「界面设置」共用的单一数据源。
// 别名/隐藏均以下列 key 为存储键：
//   - 分组 key：group:xxx
//   - 菜单项 key：路由路径（如 /customers）

export interface MenuItem {
  key: string          // 路由路径，同时作为别名/隐藏的存储键
  icon: string         // Material Symbols 图标名
  labelKey: string     // i18n 文案 key（默认名）
  permission?: string  // 需要的权限（如 customer:view）
}

export interface MenuGroup {
  key: string          // 稳定的分组标识（别名/隐藏的存储键）
  titleKey: string     // i18n 文案 key（默认分组名）
  items: MenuItem[]
}

// 系统配置入口不可隐藏，防止管理员把自己锁死在外面（后端亦会强制剔除）
export const PROTECTED_MENU_KEYS = ['/admin/settings']

export const menuGroups: MenuGroup[] = [
  {
    key: 'group:clients',
    titleKey: 'nav.groupClients',
    items: [
      { key: '/', icon: 'dashboard', labelKey: 'nav.dashboard' },
      { key: '/customers', icon: 'business', labelKey: 'nav.customers', permission: 'customer:view' },
      { key: '/customer-pool', icon: 'waves', labelKey: 'nav.customerPool', permission: 'customer:view' },
      { key: '/contacts', icon: 'contacts', labelKey: 'nav.contacts', permission: 'contact:view' },
      { key: '/leads', icon: 'trending_up', labelKey: 'nav.leads', permission: 'lead:view' },
    ],
  },
  {
    key: 'group:deals',
    titleKey: 'nav.groupDeals',
    items: [
      { key: '/opportunities', icon: 'rocket_launch', labelKey: 'nav.opportunities', permission: 'project:view' },
      { key: '/solutions', icon: 'lightbulb', labelKey: 'nav.solutions', permission: 'solution:view' },
      { key: '/quotes', icon: 'sell', labelKey: 'nav.quotes', permission: 'quote:view' },
      { key: '/contracts', icon: 'contract', labelKey: 'nav.contracts', permission: 'contract:view' },
      { key: '/change-requests', icon: 'swap_horiz', labelKey: 'nav.changeRequests', permission: 'change:view' },
      { key: '/milestones', icon: 'flag_circle', labelKey: 'nav.milestones', permission: 'delivery:view' },
    ],
  },
  {
    key: 'group:finance',
    titleKey: 'nav.groupFinance',
    items: [
      { key: '/payments', icon: 'account_balance', labelKey: 'nav.payments', permission: 'payment:view' },
      { key: '/collection', icon: 'request_quote', labelKey: 'nav.collection', permission: 'collection:view' },
      { key: '/commissions', icon: 'paid', labelKey: 'nav.commissions', permission: 'commission:view' },
      { key: '/guarantees', icon: 'verified_user', labelKey: 'nav.guarantees', permission: 'guarantee:view' },
    ],
  },
  {
    key: 'group:product-service',
    titleKey: 'nav.groupProductService',
    items: [
      { key: '/products', icon: 'inventory_2', labelKey: 'nav.products', permission: 'product:view' },
      { key: '/orders', icon: 'shopping_cart', labelKey: 'nav.orders', permission: 'order:view' },
      { key: '/tenders', icon: 'fact_check', labelKey: 'nav.tenders', permission: 'tender:view' },
      { key: '/service-tickets', icon: 'confirmation_number', labelKey: 'nav.serviceTickets', permission: 'service:view' },
      { key: '/measurements', icon: 'monitoring', labelKey: 'nav.measurements', permission: 'service:view' },
      { key: '/equipment-profile', icon: 'precision_manufacturing', labelKey: 'nav.equipmentProfile', permission: 'customer:view' },
    ],
  },
  {
    key: 'group:ops',
    titleKey: 'nav.groupOps',
    items: [
      { key: '/follow-ups', icon: 'contact_phone', labelKey: 'nav.followUps', permission: 'customer:view' },
      { key: '/sales-targets', icon: 'flag', labelKey: 'nav.salesTargets', permission: 'project:view' },
      { key: '/analytics', icon: 'analytics', labelKey: 'nav.analytics', permission: 'project:view' },
      { key: '/calendar', icon: 'calendar_month', labelKey: 'nav.calendar' },
      { key: '/tasks', icon: 'checklist', labelKey: 'nav.tasks' },
      { key: '/approvals', icon: 'task_alt', labelKey: 'nav.approvals' },
      { key: '/ai-center', icon: 'smart_toy', labelKey: 'nav.aiCenter', permission: 'project:view' },
      { key: '/knowledge-base', icon: 'menu_book', labelKey: 'nav.knowledgeBase', permission: 'project:view' },
    ],
  },
  {
    key: 'group:system',
    titleKey: 'nav.systemGroup',
    items: [
      { key: '/admin/departments', icon: 'account_tree', labelKey: 'nav.departments', permission: 'dept:view' },
      { key: '/admin/users', icon: 'group', labelKey: 'nav.users', permission: 'user:view' },
      { key: '/admin/roles', icon: 'admin_panel_settings', labelKey: 'nav.roles', permission: 'role:view' },
      { key: '/admin/audit', icon: 'history', labelKey: 'nav.auditLog', permission: 'audit:view' },
      { key: '/admin/settings', icon: 'settings', labelKey: 'nav.settings', permission: 'role:manage' },
      { key: '/admin/api-docs', icon: 'api', labelKey: 'nav.apiDocs', permission: 'role:manage' },
      { key: '/admin/openapi', icon: 'hub', labelKey: 'nav.openApi', permission: 'role:manage' },
      { key: '/admin/system-health', icon: 'monitor_heart', labelKey: 'nav.systemHealth', permission: 'role:manage' },
      { key: '/admin/dingtalk', icon: 'phonelink_ring', labelKey: 'nav.dingTalk', permission: 'role:manage' },
      { key: '/admin/data-manage', icon: 'delete_sweep', labelKey: 'nav.dataManage', permission: 'role:manage' },
    ],
  },
]
