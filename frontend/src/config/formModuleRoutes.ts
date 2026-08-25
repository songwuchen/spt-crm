/** 低代码业务模块路由 → 表单模板 code（侧栏/路由权限与审批参与对齐） */
export const FORM_MODULE_ROUTE_CODES: Record<string, string> = {
  '/drawing-requisitions': 'drawing_requisition',
  '/install-drawing-notices': 'install_drawing_notice',
  '/presale-service-notices': 'presale_service_notice',
  '/solutions': 'scheme_management',
  '/quotes': 'quote_management',
  '/pricing-checklists': 'pricing_checklist_hjqd',
  '/research-coop-cards': 'research_coop_card',
  '/tech-agreement-feedbacks': 'tech_agreement_feedback',
  '/xunhan-contract-reviews': 'xunhan_contract_review',
  '/contract-drawing-maps': 'contract_drawing_map',
  '/prod-card-supplements': 'prod_card_supplement',
  '/contract-outsource-early': 'contract_outsource_early',
  '/invoice-applications': 'invoice_application',
  '/payment-registrations': 'payment_registration',
  '/payment-registrations/dashboard': 'payment_registration',
  '/shipment-notices': 'shipment_notice',
  '/application-fields': 'application_field',
  '/application-materials': 'application_material',
  '/material-names': 'material_name',
  '/department-codes': 'department_code_base',
  '/salesperson-region-map': 'salesperson_region_map',
  '/biz-bonus-transfer': 'biz_bonus_transfer',
  '/biz-bonus-biz-initiate': 'biz_bonus_biz_initiate',
  '/commission-database': 'commission_database',
  '/biz-bonus-payment-dash-v1': 'commission_database',
  '/biz-bonus-payment-dash-v2': 'commission_database',
  '/cs-service-requests': 'cs_service_request',
  '/cs-product-replaces': 'cs_product_replace',
  '/cs-product-returns': 'cs_product_return',
  '/cs-loan-slips': 'cs_loan_slip',
  '/cs-drawing-requests': 'cs_drawing_request',
  '/cs-service-delays': 'cs_service_delay',
  '/cs-correspondences': 'cs_correspondence',
}

export function formTemplateCodeForRoute(path: string): string | undefined {
  if (FORM_MODULE_ROUTE_CODES[path]) return FORM_MODULE_ROUTE_CODES[path]
  for (const [route, code] of Object.entries(FORM_MODULE_ROUTE_CODES)) {
    if (path.startsWith(route + '/')) return code
  }
  return undefined
}
