/**
 * 审批待办 / 流程详情 → 打开原业务单据路径（含低代码表单模块深链）。
 */
import { leadReviseEditPath, isLeadReviseTodo } from '@/utils/leadWorkflow'

/** 内置低代码模块 template_code → 侧栏列表页前缀（与 router 一致） */
export const FORM_MODULE_BASE_PATHS: Record<string, string> = {
  drawing_requisition: '/drawing-requisitions',
  install_drawing_notice: '/install-drawing-notices',
  presale_service_notice: '/presale-service-notices',
  contract_drawing_map: '/contract-drawing-maps',
  application_field: '/application-fields',
  application_material: '/application-materials',
  material_name: '/material-names',
  department_code_base: '/department-codes',
  salesperson_region_map: '/salesperson-region-map',
  scheme_management: '/solutions',
  quote_management: '/quotes',
  pricing_checklist_hjqd: '/pricing-checklists',
  research_coop_card: '/research-coop-cards',
  tech_agreement_feedback: '/tech-agreement-feedbacks',
  contract_outsource_early: '/contract-outsource-early',
  biz_bonus_transfer: '/biz-bonus-transfer',
  biz_bonus_biz_initiate: '/biz-bonus-biz-initiate',
  commission_database: '/commission-database',
  prod_card_supplement: '/prod-card-supplements',
  invoice_application: '/invoice-applications',
  shipment_notice: '/shipment-notices',
  xunhan_contract_review: '/xunhan-contract-reviews',
  payment_registration: '/payment-registrations',
  contract_shipment_loan: '/contract-shipment-loans',
  cs_service_request: '/cs-service-requests',
  cs_product_replace: '/cs-product-replaces',
  cs_product_return: '/cs-product-returns',
  cs_loan_slip: '/cs-loan-slips',
  cs_drawing_request: '/cs-drawing-requests',
  cs_service_delay: '/cs-service-delays',
  cs_correspondence: '/cs-correspondences',
}

export type WorkflowBizPathInput = {
  bizType?: string | null
  bizId?: string | null
  bizRefId?: string | null
  formInstanceId?: string | null
  formCode?: string | null
  taskKind?: string | null
  nodeType?: string | null
  nodeName?: string | null
  taskId?: string | null
  mobile?: boolean
}

/** 低代码表单模块：列表页深链打开指定 instance（修订待办带 reviseTask） */
export function formModuleInstancePath(
  formCode: string,
  formInstanceId: string,
  opts?: { reviseTaskId?: string | null; edit?: boolean; mobile?: boolean },
): string | null {
  const base = FORM_MODULE_BASE_PATHS[formCode]
  if (!base) return null
  const prefix = opts?.mobile ? '/m' : ''
  const q = new URLSearchParams({ instance: formInstanceId })
  if (opts?.reviseTaskId) {
    q.set('reviseTask', opts.reviseTaskId)
    q.set('edit', '1')
  } else if (opts?.edit) {
    q.set('edit', '1')
  }
  return `${prefix}${base}?${q.toString()}`
}

/** 业务单据审批 → 完整详情页路径 */
export function bizEntityPath(
  bizType?: string | null,
  bizId?: string | null,
  bizRefId?: string | null,
  mobile = false,
): string | null {
  if (!bizType || !bizId) return null
  const p = mobile ? '/m' : ''
  const map: Record<string, string> = {
    lead: `${p}/leads/${bizId}`,
    lead_reactivation: `${p}/leads/${bizId}?react=1`,
    customer: `${p}/customers/${bizId}`,
    order: `${p}/orders/${bizId}`,
    service_ticket: `${p}/service-tickets/${bizId}`,
    contract_review: `${p}/contract-reviews/${bizId}`,
    tech_agreement_review: `${p}/tech-agreement-reviews/${bizId}`,
  }
  if (map[bizType]) return map[bizType]
  if (bizType === 'contract_version') {
    const cid = bizRefId || null
    return cid ? `${p}/contracts/${cid}` : null
  }
  return null
}

export function isReviseWorkflowTask(opts: {
  taskKind?: string | null
  nodeType?: string | null
  nodeName?: string | null
}): boolean {
  if (opts.taskKind === 'revise' || opts.nodeType === 'revise') return true
  const name = (opts.nodeName || '').trim()
  return name.includes('修改并重新提交') || name === '修改后重新提交'
}

/** 审批条目 / 流程详情 → 原单据路径；修订待办优先进可编辑页 */
export function resolveWorkflowBizPath(input: WorkflowBizPathInput): string | null {
  const mobile = input.mobile ?? false
  const revise = isReviseWorkflowTask(input)
    || (input.bizType === 'lead' && isLeadReviseTodo(input))

  if (revise && input.bizType === 'lead' && input.bizId && input.taskId) {
    return leadReviseEditPath(input.bizId, input.taskId, mobile)
  }

  if (revise && input.bizType === 'customer' && input.bizId && input.taskId) {
    const p = mobile ? '/m' : ''
    const q = new URLSearchParams()
    if (input.taskId) q.set('task', input.taskId)
    return `${p}/customers/${input.bizId}/edit?${q.toString()}`
  }

  const entity = bizEntityPath(input.bizType, input.bizId, input.bizRefId, mobile)
  if (entity) return entity

  if (input.formInstanceId && input.formCode) {
    return formModuleInstancePath(input.formCode, input.formInstanceId, {
      reviseTaskId: revise ? input.taskId : undefined,
      mobile,
    })
  }

  return null
}

export function workflowDocOpenLabel(opts: {
  isRevise?: boolean
  bizType?: string | null
  formCode?: string | null
}): string {
  if (opts.bizType === 'contract_version') return '打开合同页'
  if (opts.isRevise) return '去修改原单据'
  return '打开原单据'
}
