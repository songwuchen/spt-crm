// 菜单注册表 —— 侧边栏与「界面设置」共用的单一数据源。
// 别名/隐藏均以下列 key 为存储键：
//   - 分组 key：group:xxx
//   - 菜单项 key：路由路径（如 /customers）或子菜单容器（如 submenu:solutions）

export interface MenuItem {
  key: string          // 路由路径 / 子菜单容器 key，同时作为别名/隐藏的存储键
  icon: string         // Material Symbols 图标名
  labelKey: string     // i18n 文案 key（默认名）
  /** 单个权限，或任一命中即可 */
  permission?: string | string[]
  /** 嵌套子菜单（仅一层）；有 children 时自身不跳转路由 */
  children?: MenuItem[]
}

export interface MenuGroup {
  key: string          // 稳定的分组标识（别名/隐藏的存储键）
  titleKey: string     // i18n 文案 key（默认分组名）
  items: MenuItem[]
}

// 系统配置入口不可隐藏，防止管理员把自己锁死在外面（后端亦会强制剔除）
export const PROTECTED_MENU_KEYS = ['/admin/settings']

/** 展平所有可路由菜单项（含子菜单），用于选中态匹配 */
export function flattenMenuItems(groups: MenuGroup[] = menuGroups): MenuItem[] {
  const out: MenuItem[] = []
  for (const g of groups) {
    for (const item of g.items) {
      if (item.children?.length) out.push(...item.children)
      else out.push(item)
    }
  }
  return out
}

export const menuGroups: MenuGroup[] = [
  {
    key: 'group:inbox',
    titleKey: 'nav.groupInbox',
    items: [
      { key: '/approvals', icon: 'task_alt', labelKey: 'nav.approvals' },
      { key: '/notifications', icon: 'notifications', labelKey: 'nav.notifications' },
    ],
  },
  {
    key: 'group:clients',
    titleKey: 'nav.groupClients',
    items: [
      { key: '/', icon: 'dashboard', labelKey: 'nav.dashboard' },
      { key: '/customers', icon: 'business', labelKey: 'nav.customers', permission: 'customer:view' },
      { key: '/customer-pool', icon: 'waves', labelKey: 'nav.customerPool', permission: 'customer:view' },
      { key: '/contacts', icon: 'contacts', labelKey: 'nav.contacts', permission: 'contact:view' },
      { key: '/leads', icon: 'trending_up', labelKey: 'nav.leads', permission: 'lead:view' },
      { key: '/lead-reactivations', icon: 'schedule', labelKey: 'nav.leadReactivations', permission: 'lead:view' },
    ],
  },
  {
    key: 'group:deals',
    titleKey: 'nav.groupDeals',
    items: [
      { key: '/opportunities', icon: 'rocket_launch', labelKey: 'nav.opportunities', permission: 'project:view' },
      {
        key: 'submenu:solutions',
        icon: 'lightbulb',
        labelKey: 'nav.solutions',
        children: [
          { key: '/drawing-requisitions', icon: 'draft', labelKey: 'nav.drawingRequisitions', permission: 'form_data:view' },
          { key: '/install-drawing-notices', icon: 'architecture', labelKey: 'nav.installDrawingNotices', permission: 'form_data:view' },
          { key: '/presale-service-notices', icon: 'engineering', labelKey: 'nav.presaleServiceNotices', permission: 'form_data:view' },
        ],
      },
      { key: '/quotes', icon: 'sell', labelKey: 'nav.quotes', permission: 'form_data:view' },
      { key: '/pricing-checklists', icon: 'request_quote', labelKey: 'nav.pricingChecklists', permission: 'form_data:view' },
      { key: '/research-coop-cards', icon: 'hub', labelKey: 'nav.researchCoopCards', permission: 'form_data:view' },
      { key: '/tech-agreement-feedbacks', icon: 'rate_review', labelKey: 'nav.techAgreementFeedbacks', permission: 'form_data:view' },
      { key: '/contract-reviews', icon: 'fact_check', labelKey: 'nav.contractReviews', permission: 'contract_review:view' },
      { key: '/xunhan-contract-reviews', icon: 'fact_check', labelKey: 'nav.xunhanContractReviews', permission: 'form_data:view' },
      { key: '/tech-agreement-reviews', icon: 'description', labelKey: 'nav.techAgreementReviews', permission: 'tech_agreement_review:view' },
      { key: '/contract-drawing-maps', icon: 'map', labelKey: 'nav.contractDrawingMaps', permission: 'form_data:view' },
      { key: '/contracts', icon: 'contract', labelKey: 'nav.contracts', permission: 'contract:view' },
      { key: '/contracts/dashboard', icon: 'insert_chart', labelKey: 'nav.contractManagementDashboard', permission: 'contract:view' },
      { key: '/prod-card-supplements', icon: 'assignment', labelKey: 'nav.prodCardSupplements', permission: 'form_data:view' },
      { key: '/contract-outsource-early', icon: 'schedule', labelKey: 'nav.contractOutsourceEarly', permission: 'form_data:view' },
      { key: '/invoice-applications', icon: 'receipt_long', labelKey: 'nav.invoiceApplications', permission: 'form_data:view' },
      { key: '/payment-registrations', icon: 'payments', labelKey: 'nav.paymentRegistrations', permission: 'form_data:view' },
      { key: '/payment-registrations/dashboard', icon: 'insert_chart', labelKey: 'nav.paymentRegistrationDashboard', permission: 'form_data:view' },
      { key: '/shipment-notices', icon: 'local_shipping', labelKey: 'nav.shipmentNotices', permission: 'form_data:view' },
      { key: '/change-requests', icon: 'swap_horiz', labelKey: 'nav.changeRequests', permission: 'change:view' },
      { key: '/milestones', icon: 'flag_circle', labelKey: 'nav.milestones', permission: 'delivery:view' },
    ],
  },
  {
    key: 'group:master-data',
    titleKey: 'nav.groupMasterData',
    items: [
      { key: '/application-fields', icon: 'category', labelKey: 'nav.applicationFields', permission: 'form_data:view' },
      { key: '/application-materials', icon: 'inventory_2', labelKey: 'nav.applicationMaterials', permission: 'form_data:view' },
      { key: '/material-names', icon: 'label', labelKey: 'nav.materialNames', permission: 'form_data:view' },
      { key: '/department-codes', icon: 'apartment', labelKey: 'nav.departmentCodes', permission: 'form_data:view' },
      { key: '/salesperson-region-map', icon: 'group', labelKey: 'nav.salespersonRegionMap', permission: 'form_data:view' },
    ],
  },
  {
    key: 'group:finance',
    titleKey: 'nav.groupFinance',
    items: [
      { key: '/payments', icon: 'account_balance', labelKey: 'nav.payments', permission: 'payment:view' },
      { key: '/collection', icon: 'request_quote', labelKey: 'nav.collection', permission: 'collection:view' },
      { key: '/commissions', icon: 'paid', labelKey: 'nav.commissions', permission: 'commission:view' },
      { key: '/biz-bonus-transfer', icon: 'paid', labelKey: 'nav.bizBonusTransfer', permission: 'form_data:view' },
      { key: '/biz-bonus-biz-initiate', icon: 'send', labelKey: 'nav.bizBonusBizInitiate', permission: 'form_data:view' },
      { key: '/commission-database', icon: 'inventory_2', labelKey: 'nav.commissionDatabase', permission: 'form_data:view' },
      { key: '/biz-bonus-payment-dash-v1', icon: 'insert_chart', labelKey: 'nav.bizBonusPaymentDashV1', permission: 'form_data:view' },
      { key: '/biz-bonus-payment-dash-v2', icon: 'insert_chart', labelKey: 'nav.bizBonusPaymentDashV2', permission: 'form_data:view' },
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
      { key: '/cs-service-requests', icon: 'support_agent', labelKey: 'nav.csServiceRequests', permission: 'form_data:view' },
      { key: '/cs-product-replaces', icon: 'swap_horiz', labelKey: 'nav.csProductReplaces', permission: 'form_data:view' },
      { key: '/cs-product-returns', icon: 'assignment_return', labelKey: 'nav.csProductReturns', permission: 'form_data:view' },
      { key: '/cs-loan-slips', icon: 'receipt_long', labelKey: 'nav.csLoanSlips', permission: 'form_data:view' },
      { key: '/cs-drawing-requests', icon: 'image', labelKey: 'nav.csDrawingRequests', permission: 'form_data:view' },
      { key: '/cs-service-delays', icon: 'schedule', labelKey: 'nav.csServiceDelays', permission: 'form_data:view' },
      { key: '/cs-correspondences', icon: 'mail', labelKey: 'nav.csCorrespondences', permission: 'form_data:view' },
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
      { key: '/ai-center', icon: 'smart_toy', labelKey: 'nav.aiCenter', permission: 'project:view' },
      { key: '/knowledge-base', icon: 'menu_book', labelKey: 'nav.knowledgeBase', permission: 'project:view' },
    ],
  },
  {
    // 扩展平台是表单/流程设计入口，仅系统管理员可见。
    // 业务填报、审批中心仍走各自模块，不依赖本组。
    key: 'group:lowcode',
    titleKey: 'nav.groupLowcode',
    items: [
      { key: '/lowcode/forms', icon: 'dynamic_form', labelKey: 'nav.lowcodeForms', permission: 'role:manage' },
      { key: '/lowcode/workflows', icon: 'account_tree', labelKey: 'nav.lowcodeWorkflows', permission: 'role:manage' },
      // 审批入口统一到主菜单「审批中心」，避免双入口混淆
      { key: '/lowcode/dashboards', icon: 'insert_chart', labelKey: 'nav.lowcodeDashboards', permission: 'role:manage' },
      { key: '/lowcode/entity-fields', icon: 'tune', labelKey: 'nav.lowcodeEntityFields', permission: 'role:manage' },
    ],
  },
  {
    key: 'group:system',
    titleKey: 'nav.systemGroup',
    items: [
      { key: '/admin/departments', icon: 'account_tree', labelKey: 'nav.departments', permission: 'dept:view' },
      { key: '/admin/users', icon: 'group', labelKey: 'nav.users', permission: 'user:view' },
      { key: '/admin/roles', icon: 'admin_panel_settings', labelKey: 'nav.roles', permission: 'role:view' },
      { key: '/admin/pickable-scopes', icon: 'groups', labelKey: 'nav.pickableScopes', permission: 'role:view' },
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
