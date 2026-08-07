// 图纸 / 方案 / 生产卡 / 开票 / 收款：分区布局 + 栅格 span（对齐简道云 lineWidth，×2 为 antd Col span）
import type { FieldDefinition } from '@/types/lowcode'

export type DrawingSection = { title: string; fieldIds: string[] }

export const DRAWING_FORM_LAYOUT: Record<string, {
  sections: DrawingSection[]
  /** fieldId -> antd Col span (default 12 for short, 24 for long) */
  spans?: Record<string, number>
  contentMaxWidth?: number
  /**
   * 列表展开的明细表字段 id（简道云式主表 rowSpan + 明细多列）。
   * 也可用字段 props.list_expand=true 声明；二者任一即可。
   */
  listExpandDetail?: string
}> = {
  drawing_requisition: {
    contentMaxWidth: 1080,
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'apply_datetime', 'department', 'applicant', 'involve_std_drawing',
          'order_person', 'order_person_text', 'contract_no', 'apply_reason',
          'designer', 'designer_text', 'product_model',
        ],
      },
      {
        title: '图纸传递与解密',
        fieldIds: ['transfer_channel', 'need_decrypt', 'need_decrypt_note', 'paper_print_tip'],
      },
      {
        title: '图纸与附件',
        fieldIds: ['drawing_type', 'attachment_name', 'attachments', 'images'],
      },
      {
        title: '设计分派',
        fieldIds: [
          'design_dispatch', 'transfer_packaging_users', 'design_assignees',
          'offices', 'order_date', 'need_gm_approval',
        ],
      },
    ],
    spans: {
      apply_reason: 24, paper_print_tip: 24, attachments: 24, images: 24,
    },
  },
  install_drawing_notice: {
    contentMaxWidth: 1100,
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'apply_datetime', 'project_no', 'is_new_project', 'sales_person',
          'customer_name', 'matter', 'applicant', 'department', 'order_person',
          'order_person_text', 'dept_code', 'is_xiaomeng', 'design_card_no',
        ],
      },
      {
        title: '下图与领图',
        fieldIds: [
          'drawing_issue_type', 'drawing_types', 'need_decrypt', 'pickup_purpose',
          'apply_or_change', 'apply_reason_star', 'biz_feedback', 'lose_bid_reason',
        ],
      },
      {
        title: '安装图通知单及设计卡',
        fieldIds: [
          'card_date', 'pre_designers', 'require_draw_date', 'product_model',
        ],
      },
      {
        title: '出方案与安装条件',
        fieldIds: [
          'scheme_detail', 'install_env', 'install_position', 'foundation_drawing',
          'install_method', 'scheme_material', 'non_scheme_material',
        ],
      },
      {
        title: '附件与设计分派',
        fieldIds: [
          'attachment_names', 'attachments', 'attachments_no_image', 'design_dispatch',
          'transfer_packaging_users', 'design_assignees', 'need_submit_drawing',
          'offices_multi', 'order_date', 'transfer_sw_lwt',
        ],
      },
      {
        title: '评价打分（审批填写）',
        fieldIds: [
          'score_attitude', 'score_progress', 'score_skill', 'score_total',
          'score_date', 'remark', 'attention',
        ],
      },
    ],
    spans: {
      scheme_detail: 24, install_env: 24, scheme_material: 24, non_scheme_material: 24,
      change_scheme: 24, apply_or_change: 24, apply_reason_star: 24, remark: 24, attention: 24,
      attachments: 24, attachments_no_image: 24,
    },
  },
  // 方案管理：scheme_type 分流；独有字段靠规则显隐，布局按类型分区列出
  scheme_management: {
    contentMaxWidth: 1100,
    sections: [
      {
        title: '方案类型',
        fieldIds: ['scheme_type', 'related_project', 'related_customer'],
      },
      {
        title: '共用基本信息',
        fieldIds: [
          'apply_datetime', 'department', 'applicant', 'order_person',
          'apply_or_change',
          'product_model', 'design_dispatch', 'transfer_packaging_users',
          'design_assignees', 'order_date', 'images',
        ],
      },
      {
        title: '有合同号 · 领用',
        fieldIds: [
          'involve_std_drawing', 'contract_no', 'apply_reason', 'designer',
          'transfer_channel', 'paper_print_tip', 'drawing_type',
          'attachment_name', 'attachments', 'offices', 'need_gm_approval',
        ],
      },
      {
        title: '无合同号 · 投标/安装图',
        fieldIds: [
          'customer_name', 'matter',
          'dept_code', 'is_xiaomeng', 'design_card_no', 'drawing_issue_type', 'drawing_types',
          'pickup_purpose', 'apply_reason_star', 'biz_feedback',
          'lose_bid_reason', 'card_date', 'pre_designers', 'require_draw_date',
          'scheme_detail', 'install_env', 'install_position',
          'foundation_drawing', 'install_method', 'scheme_material',
          'attention', 'attachment_names', 'attachments_no_image',
          'offices_multi', 'transfer_sw_lwt', 'need_gm_approval',
        ],
      },
      {
        title: '评价打分（审批填写）',
        fieldIds: [
          'score_attitude', 'score_progress', 'score_skill', 'score_total', 'score_date', 'remark',
        ],
      },
    ],
    spans: {
      scheme_type: 24,
      related_project: 24,
      related_customer: 24,
      apply_reason: 24, paper_print_tip: 24, attachments: 24, images: 24,
      scheme_detail: 24, install_env: 24, scheme_material: 24,
      apply_or_change: 24, apply_reason_star: 24, remark: 24, attention: 24,
      attachments_no_image: 24,
    },
  },
  // 生产卡/补充流程：分区对齐 JDY 分隔条；span = lineWidth×2
  prod_card_supplement: {
    contentMaxWidth: 1100,
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'card_date', 'department', 'submitter', 'is_supplement',
          'involve_outsource', 'is_finance_only', 'is_shipped', 'involve_amount_change',
          'is_unit_change', 'is_robot', 'f_240503', 'increase_cost',
          'need_research_drawing', 'product_type', 'is_turnkey', 'responsible_party',
        ],
      },
      {
        title: '补充 / 合同信息',
        fieldIds: [
          'drawing_no_query', 'no_sales_person', 'no_drawing_no',
          'contract_no_select', 'paint_req_supplement',
          'yes_contract_no', 'yes_sales_person', 'yes_customer_name',
          'customer_sales_select', 'description', 'region_manager',
        ],
      },
      {
        title: '车间填写',
        fieldIds: ['std_room_fill', 'elec_workshop_fill'],
      },
      {
        title: '技术协议与附件',
        fieldIds: [
          'need_dispatch', 'need_elec_workshop', 'has_tech_agreement', 'tech_agreement_std',
          'attachments', 'images', 'confirm_agreement',
        ],
      },
      {
        title: '设计指派填写',
        fieldIds: [
          'design_dispatch', 'transfer_packaging_users', 'design_assignees', 'offices',
          'order_datetime', 'order_type', 'field',
          'has_install_project', 'f_251128', 'install_project_no', 'f_0414',
        ],
      },
      {
        title: '生产卡通知单上的内容',
        fieldIds: [
          'prod_card_line_items', 'packaging_req', 'project_name', 'paint_req',
          'tech_params', 'no_warranty_period', 'special_reminder',
          'remark_prod_card', 'special_reminder_multi',
        ],
      },
      {
        title: '合同技术协议评审',
        fieldIds: [
          'has_contract_tech_review', 'select_contract_tech_review', 'contract_tech_review_sn',
        ],
      },
    ],
    spans: {
      card_date: 6, department: 6, submitter: 6, is_supplement: 6,
      involve_outsource: 6, is_finance_only: 6, is_shipped: 6, involve_amount_change: 6,
      is_unit_change: 6, is_robot: 6, f_240503: 6, increase_cost: 6,
      need_research_drawing: 6, product_type: 6, is_turnkey: 6, responsible_party: 6,
      drawing_no_query: 24, no_sales_person: 6, no_drawing_no: 6,
      contract_no_select: 24, paint_req_supplement: 24,
      yes_contract_no: 6, yes_sales_person: 6, yes_customer_name: 6,
      customer_sales_select: 12, description: 24, region_manager: 12,
      std_room_fill: 24, elec_workshop_fill: 24,
      need_dispatch: 24, need_elec_workshop: 6, has_tech_agreement: 6, tech_agreement_std: 12,
      attachments: 12, images: 12, confirm_agreement: 24,
      design_dispatch: 12, transfer_packaging_users: 12, design_assignees: 12, offices: 12,
      order_datetime: 8, order_type: 8, field: 8,
      has_install_project: 6, f_251128: 24, install_project_no: 24, f_0414: 24,
      prod_card_line_items: 24,
      packaging_req: 8, project_name: 8, paint_req: 8,
      tech_params: 8, no_warranty_period: 6, special_reminder: 12,
      remark_prod_card: 8, special_reminder_multi: 8,
      has_contract_tech_review: 12, select_contract_tech_review: 12, contract_tech_review_sn: 12,
    },
  },
  // 开票申请
  invoice_application: {
    contentMaxWidth: 1080,
    sections: [
      {
        title: '基本信息',
        fieldIds: [
          'serial_no', 'apply_date', 'department', 'drawing_no_select',
          'drawing_no', 'customer_name', 'dept_contract_no', 'customer_no',
          'sales_person', 'contract_data',
        ],
      },
      {
        title: '合同明细与合计',
        fieldIds: [
          'contract_lines_new', 'contract_lines_change',
          'total_amount', 'total_amount_adjusted', 'customer_code',
        ],
      },
      {
        title: '开票与附件',
        fieldIds: [
          'invoice_datetime', 'invoice_special_req', 'invoice_no', 'remark',
          'invoice_email', 'attachments', 'images',
        ],
      },
    ],
    spans: {
      serial_no: 6, apply_date: 6, department: 6, drawing_no_select: 6,
      drawing_no: 6, customer_name: 12, dept_contract_no: 6, customer_no: 6,
      sales_person: 6, contract_data: 24,
      contract_lines_new: 24, contract_lines_change: 24,
      total_amount: 8, total_amount_adjusted: 8, customer_code: 8,
      invoice_datetime: 6, invoice_special_req: 18, invoice_no: 6, remark: 18,
      invoice_email: 8, attachments: 8, images: 8,
    },
  },
  // 收款登记（内勤填写对齐 JDY separator）
  payment_registration: {
    contentMaxWidth: 1080,
    listExpandDetail: 'payment_details',
    sections: [
      {
        title: '来款信息',
        fieldIds: [
          'payment_no', 'payment_date', 'customer_name', 'department',
          'payment_details', 'payment_total',
        ],
      },
      {
        title: '内勤填写',
        fieldIds: [
          'sales_person', 'payment_allocation', 'alloc_total',
          'discount_docs', 'penalty_docs', 'images', 'remark_2',
        ],
      },
    ],
    spans: {
      payment_no: 6, payment_date: 6, customer_name: 6, department: 6,
      payment_details: 24, payment_total: 12,
      sales_person: 12, payment_allocation: 24, alloc_total: 6,
      discount_docs: 6, penalty_docs: 6, images: 6, remark_2: 24,
    },
  },
}

/** 解析列表应展开的明细表：字段 props.list_expand 优先，其次布局 listExpandDetail */
export function resolveListExpandDetail(
  fields: FieldDefinition[],
  templateCode?: string,
): FieldDefinition | undefined {
  const byProp = fields.find(
    (f) => f.type === 'detail_table' && !!(f.props as { list_expand?: boolean } | undefined)?.list_expand,
  )
  if (byProp) return byProp
  const id = templateCode ? DRAWING_FORM_LAYOUT[templateCode]?.listExpandDetail : undefined
  if (!id) return undefined
  return fields.find((f) => f.id === id && f.type === 'detail_table')
}

const SHORT_TYPES = new Set([
  'text', 'select', 'radio', 'person', 'person_multi',
  'department', 'department_multi', 'date', 'datetime', 'number',
  'amount', 'multi_select', 'switch', 'formula', 'auto_number', 'project', 'contract', 'customer',
])

function defaultSpan(field: FieldDefinition): number {
  if (field.type === 'detail_table' || field.type === 'textarea' || field.type === 'file'
    || field.type === 'image' || field.type === 'checkbox' || field.type === 'rich_text'
    || field.type === 'address' || field.type === 'cascade' || field.type === 'signature') {
    return 24
  }
  if (SHORT_TYPES.has(field.type)) return 12
  return 24
}

/** Inject section markers + apply spans; keep unknown fields at end under 「其它」 */
export function applyDrawingFormLayout(
  templateCode: string | undefined,
  fields: FieldDefinition[],
): FieldDefinition[] {
  if (!templateCode) return fields
  const layout = DRAWING_FORM_LAYOUT[templateCode]
  if (!layout) return fields

  const byId = new Map(fields.map((f) => [f.id, f]))
  const used = new Set<string>()
  const out: FieldDefinition[] = []
  const spans = layout.spans || {}

  const withSpan = (f: FieldDefinition): FieldDefinition => ({
    ...f,
    span: spans[f.id] ?? f.span ?? defaultSpan(f),
  })

  for (const sec of layout.sections) {
    const matched = sec.fieldIds
      .map((id) => byId.get(id))
      .filter((f): f is FieldDefinition => !!f)
    if (!matched.length) continue
    out.push({
      id: `__section_${sec.title}`,
      type: 'section',
      label: sec.title,
      span: 24,
    })
    for (const f of matched) {
      used.add(f.id)
      out.push(withSpan(f))
    }
  }

  const rest = fields.filter((f) => !used.has(f.id))
  if (rest.length) {
    out.push({
      id: '__section_其它',
      type: 'section',
      label: '其它',
      span: 24,
    })
    for (const f of rest) out.push(withSpan(f))
  }
  return out
}
