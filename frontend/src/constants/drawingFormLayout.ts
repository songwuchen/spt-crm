// 合同图纸领用 / 安装图设计通知：分区布局 + 栅格 span（对齐简道云观感）
import type { FieldDefinition } from '@/types/lowcode'

export type DrawingSection = { title: string; fieldIds: string[] }

export const DRAWING_FORM_LAYOUT: Record<string, {
  sections: DrawingSection[]
  /** fieldId -> antd Col span (default 12 for short, 24 for long) */
  spans?: Record<string, number>
  contentMaxWidth?: number
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
          'card_date', 'pre_designers', 'require_draw_date', 'product_model', 'pre_designer_text',
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
        title: '评价打分',
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
}

const SHORT_TYPES = new Set([
  'text', 'select', 'radio', 'person', 'person_multi',
  'department', 'department_multi', 'date', 'datetime', 'number',
  'amount', 'multi_select', 'switch', 'formula', 'auto_number',
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
