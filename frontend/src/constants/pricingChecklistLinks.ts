/** 核价清单传递：关联选择字段带出的目标字段（清空时一并清掉）。 */
export const PRICING_CHECKLIST_LINKS: Record<string, { dests: string[] }> = {
  link_install: {
    dests: [
      'install_serial_no', 'install_design_card_no', 'install_order_person',
      'install_applicant', 'install_department',
      'summary_serial_no', 'design_card_no', 'contract_no',
      'order_person', 'applicant', 'business_dept',
    ],
  },
  link_requisition: {
    dests: [
      'req_serial_no', 'req_contract_no', 'req_applicant',
      'req_order_person', 'req_department',
      'summary_serial_no', 'design_card_no', 'contract_no',
      'order_person', 'applicant', 'business_dept',
    ],
  },
  link_cs_drawing: {
    dests: [
      'cs_serial_no', 'cs_contract_no', 'cs_order_person',
      'cs_applicant', 'cs_department',
      'summary_serial_no', 'design_card_no', 'contract_no',
      'order_person', 'applicant', 'business_dept',
    ],
  },
  link_coop_card: {
    dests: [
      'coop_serial_no', 'coop_contract_no', 'coop_order_person',
      'coop_applicant', 'coop_order_dept',
      'summary_serial_no', 'design_card_no', 'contract_no',
      'order_person', 'applicant', 'business_dept',
    ],
  },
}

/** 切换流程名称时清掉所有关联选择及带出字段。 */
export function pricingChecklistAllClearKeys(): string[] {
  const keys = new Set<string>(Object.keys(PRICING_CHECKLIST_LINKS))
  for (const spec of Object.values(PRICING_CHECKLIST_LINKS)) {
    for (const d of spec.dests) keys.add(d)
  }
  return [...keys]
}
