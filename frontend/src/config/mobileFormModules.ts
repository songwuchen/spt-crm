/** 移动端业务表单模块（与 PC FormModule 路由一一对应） */
export interface MobileFormModuleDef {
  /** PC 侧栏路径，如 /prod-card-supplements */
  basePath: string
  templateCode: string
  title: string
  dashboardPath?: string
  legacySchemeList?: boolean
}

export const MOBILE_FORM_MODULES: MobileFormModuleDef[] = [
  { basePath: '/drawing-requisitions', templateCode: 'drawing_requisition', title: '合同图纸领用' },
  { basePath: '/install-drawing-notices', templateCode: 'install_drawing_notice', title: '安装图设计通知' },
  { basePath: '/presale-service-notices', templateCode: 'presale_service_notice', title: '售前服务通知' },
  { basePath: '/contract-drawing-maps', templateCode: 'contract_drawing_map', title: '合同图纸对应表' },
  { basePath: '/application-fields', templateCode: 'application_field', title: '应用领域' },
  { basePath: '/application-materials', templateCode: 'application_material', title: '应用物料' },
  { basePath: '/material-names', templateCode: 'material_name', title: '物料名称' },
  { basePath: '/department-codes', templateCode: 'department_code_base', title: '部门编号基础表' },
  { basePath: '/salesperson-region-map', templateCode: 'salesperson_region_map', title: '业务员区域经理对照' },
  { basePath: '/solutions', templateCode: 'scheme_management', title: '方案管理（历史）', legacySchemeList: true },
  { basePath: '/quotes', templateCode: 'quote_management', title: '报价管理' },
  { basePath: '/pricing-checklists', templateCode: 'pricing_checklist_hjqd', title: '核价清单传递' },
  { basePath: '/research-coop-cards', templateCode: 'research_coop_card', title: '中央研究院协同卡' },
  { basePath: '/tech-agreement-feedbacks', templateCode: 'tech_agreement_feedback', title: '技术协议反馈单' },
  { basePath: '/contract-outsource-early', templateCode: 'contract_outsource_early', title: '合同外购件提前安排流程' },
  { basePath: '/biz-bonus-transfer', templateCode: 'biz_bonus_transfer', title: '业务奖金流转单' },
  { basePath: '/biz-bonus-biz-initiate', templateCode: 'biz_bonus_biz_initiate', title: '业务奖金流转—业务发起' },
  {
    basePath: '/commission-database',
    templateCode: 'commission_database',
    title: '提成数据库',
    dashboardPath: '/m/biz-bonus-payment-dash-v1',
  },
  { basePath: '/prod-card-supplements', templateCode: 'prod_card_supplement', title: '生产卡/补充流程' },
  { basePath: '/invoice-applications', templateCode: 'invoice_application', title: '开票申请' },
  { basePath: '/shipment-notices', templateCode: 'shipment_notice', title: '发货通知' },
  { basePath: '/xunhan-contract-reviews', templateCode: 'xunhan_contract_review', title: '迅焊公司合同评审' },
  {
    basePath: '/payment-registrations',
    templateCode: 'payment_registration',
    title: '收款登记',
    dashboardPath: '/m/payment-registrations/dashboard',
  },
  {
    basePath: '/contract-shipment-loans',
    templateCode: 'contract_shipment_loan',
    title: '合同及发货借据流程',
    dashboardPath: '/m/contract-shipment-loans/shipment-dashboard',
  },
  { basePath: '/cs-service-requests', templateCode: 'cs_service_request', title: '客户服务申请及反馈' },
  { basePath: '/cs-product-replaces', templateCode: 'cs_product_replace', title: '售出产品更换（补发）' },
  { basePath: '/cs-product-returns', templateCode: 'cs_product_return', title: '售出产品/工具退回' },
  { basePath: '/cs-loan-slips', templateCode: 'cs_loan_slip', title: '客服借据' },
  { basePath: '/cs-drawing-requests', templateCode: 'cs_drawing_request', title: '客服领图' },
  { basePath: '/cs-service-delays', templateCode: 'cs_service_delay', title: '客户服务延期申请' },
  { basePath: '/cs-correspondences', templateCode: 'cs_correspondence', title: '客服往来函件' },
]

/** /m 下路由片段，如 prod-card-supplements */
export function mobileFormModuleRouteSegment(basePath: string): string {
  return basePath.replace(/^\//, '')
}
