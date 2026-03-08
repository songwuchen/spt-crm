/**
 * i18n Locale — Simplified Chinese (zh-CN)
 *
 * Base locale file for internationalization preparation.
 * All UI strings should eventually reference keys from this file.
 *
 * Usage:
 *   import { t } from '@/locales'
 *   <span>{t('common.save')}</span>
 */

const zhCN = {
  // -------- Common --------
  common: {
    save: '保存',
    cancel: '取消',
    confirm: '确认',
    delete: '删除',
    edit: '编辑',
    create: '新建',
    search: '搜索',
    filter: '筛选',
    reset: '重置',
    export: '导出',
    import: '导入',
    refresh: '刷新',
    loading: '加载中...',
    noData: '暂无数据',
    success: '操作成功',
    failed: '操作失败',
    yes: '是',
    no: '否',
    back: '返回',
    submit: '提交',
    more: '更多',
    all: '全部',
    total: '共',
    items: '条',
    actions: '操作',
    status: '状态',
    remark: '备注',
    createdAt: '创建时间',
    updatedAt: '更新时间',
    createdBy: '创建人',
  },

  // -------- Auth --------
  auth: {
    login: '登录',
    logout: '退出登录',
    username: '用户名',
    password: '密码',
    loginTitle: '登录 SPT-CRM',
    loginSubtitle: '智能销售项目管理平台',
    rememberMe: '记住我',
    forgotPassword: '忘记密码？',
    loginFailed: '登录失败，请检查用户名和密码',
  },

  // -------- Navigation --------
  nav: {
    businessGroup: '业务管理',
    systemGroup: '系统设置',
    dashboard: '工作台',
    customers: '客户管理',
    customerPool: '客户公海',
    contacts: '联系人',
    leads: '线索管理',
    opportunities: '商机管理',
    kanban: '看板视图',
    products: '产品目录',
    followUps: '跟进记录',
    payments: '回款管理',
    serviceTickets: '售后工单',
    salesTargets: '销售目标',
    renewals: '续约管理',
    analytics: '报表中心',
    calendar: '日程日历',
    changeRequests: '变更管理',
    milestones: '交付里程碑',
    tasks: '待办任务',
    approvals: '审批中心',
    aiCenter: 'AI 任务中心',
    notifications: '通知中心',
    admin: '系统管理',
    departments: '部门管理',
    users: '用户管理',
    roles: '角色权限',
    auditLog: '审计日志',
    settings: '系统配置',
    apiDocs: 'API 文档',
    profile: '个人中心',
  },

  // -------- Customer --------
  customer: {
    title: '客户管理',
    name: '客户名称',
    shortName: '简称',
    level: '客户等级',
    industry: '行业',
    region: '区域',
    owner: '客户负责人',
    contactPhone: '联系电话',
    address: '地址',
    status: '客户状态',
    createCustomer: '新建客户',
    editCustomer: '编辑客户',
    customerDetail: '客户详情',
  },

  // -------- Lead --------
  lead: {
    title: '线索管理',
    name: '线索名称',
    source: '线索来源',
    status: '线索状态',
    assignee: '分配人',
    convertToCustomer: '转为客户',
    convertToOpportunity: '转为商机',
    createLead: '新建线索',
  },

  // -------- Opportunity / Project --------
  opportunity: {
    title: '商机管理',
    name: '商机名称',
    customer: '客户',
    stage: '阶段',
    amount: '预期金额',
    probability: '赢率',
    owner: '负责人',
    expectedCloseDate: '预期成交日',
    createOpportunity: '新建商机',
    editOpportunity: '编辑商机',
    detail: '商机详情',
    stages: {
      S1: '线索确认',
      S2: '需求分析',
      S3: '方案报价',
      S4: '商务谈判',
      S5: '合同签署',
      S6: '交付验收',
    },
    riskLevel: {
      H: '高风险',
      M: '中风险',
      L: '低风险',
    },
  },

  // -------- Quote --------
  quote: {
    title: '报价管理',
    quoteNo: '报价编号',
    version: '版本',
    amount: '报价金额',
    costTotal: '成本合计',
    marginRate: '毛利率',
    status: '状态',
    lineItems: '行项明细',
    createVersion: '新建版本',
    aiReview: 'AI 审核',
  },

  // -------- Contract --------
  contract: {
    title: '合同管理',
    contractNo: '合同编号',
    amount: '合同金额',
    signDate: '签署日期',
    startDate: '开始日期',
    endDate: '结束日期',
    status: '合同状态',
    createVersion: '新建版本',
    aiReview: 'AI 审核',
  },

  // -------- Payment --------
  payment: {
    title: '回款管理',
    invoices: '开票记录',
    plans: '回款计划',
    records: '收款记录',
    planNo: '计划编号',
    dueDate: '到期日',
    amount: '金额',
    status: '状态',
    overdue: '已逾期',
    pending: '待收',
    paid: '已收',
  },

  // -------- Approval --------
  approval: {
    title: '审批中心',
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回',
    approve: '通过',
    reject: '驳回',
    comment: '审批意见',
    submitApproval: '提交审批',
    history: '审批历史',
  },

  // -------- Service --------
  service: {
    title: '服务工单',
    ticketNo: '工单编号',
    priority: '优先级',
    assignee: '处理人',
    status: '工单状态',
    createTicket: '新建工单',
  },

  // -------- AI Center --------
  ai: {
    title: 'AI 中心',
    riskAnalysis: '风险分析',
    customerProfile: '客户画像',
    winProbability: '赢率预测',
    nextActions: '行动建议',
    quoteReview: '报价审核',
    contractReview: '合同审核',
    activitySummary: '活动总结',
    similarProjects: '相似商机',
    analyzing: 'AI 分析中...',
    promptTemplates: 'Prompt 模板',
    taskHistory: '任务历史',
  },

  // -------- Notification --------
  notification: {
    title: '通知中心',
    markRead: '标记已读',
    markAllRead: '全部已读',
    unread: '未读',
    read: '已读',
    viewAll: '查看全部通知',
    noNotifications: '暂无通知',
    types: {
      approval_pending: '审批待处理',
      approval_decided: '审批已决定',
      approval_sla_overdue: '审批超时',
      stage_advance: '阶段推进',
      stage_change: '阶段变化',
      contract_signed: '合同签署',
      ticket_assigned: '工单分配',
      payment_overdue: '回款逾期',
      payment_received: '收到回款',
      ai_task_complete: 'AI 完成',
      gate_blocked: '门禁拦截',
      system: '系统通知',
    },
  },

  // -------- Admin --------
  admin: {
    settings: '系统设置',
    stageGate: '阶段Gate',
    marginPolicy: '毛利红线',
    featureToggles: '功能开关',
    aiPolicy: 'AI策略',
    approvalPolicy: '审批策略',
    integration: '集成配置',
    auditLog: '审计日志',
    departments: '部门管理',
    users: '用户管理',
    roles: '角色管理',
  },

  // -------- Analytics --------
  analytics: {
    title: '数据分析',
    salesFunnel: '销售漏斗',
    trend: '趋势分析',
    collection: '回款分析',
    leaderboard: '排行榜',
    overview: '概览',
  },
} as const

export type LocaleKeys = typeof zhCN
export default zhCN
