/** 简道云销售中心「合同技术协议评审 HTJSXY」字段分区
 *
 * 流程 optAuth（1=可见 2=可写）：
 * - 发起可写：申请人/业务员/部门/电控/项目/重量/呆滞/智能化/核价/签订依据/参考合同号/前期沟通人/附件/备注…
 * - 审批可写：设计审批（总工审批节点）、设计审批2（设计审批1 节点）
 * - 「是否有异议」未进任何节点 optAuth，按表单位置归入审批信息区
 */

export type TarFieldSource = 'native' | 'form'
export type TarFillStage = 'initiator' | 'approver'

export type TarWidget =
  | 'text'
  | 'textarea'
  | 'date'
  | 'radio'
  | 'combo'
  | 'person'
  | 'person_multi'
  | 'department'

export interface TarOption {
  value: string
  label: string
}

export interface TarFieldDef {
  key: string
  label: string
  source: TarFieldSource
  widget?: TarWidget
  options?: TarOption[]
  required?: boolean
  /** 默认 initiator；approver = 简道云审批节点填写，发起表单不展示 */
  fillStage?: TarFillStage
}

export interface TarSection {
  key: string
  title: string
  fields: TarFieldDef[]
  afterSlot?: 'approve_files' | 'tech_files'
  fieldsAfterSlot?: TarFieldDef[]
  /** 整区仅审批信息（详情展示） */
  fillStage?: TarFillStage
}

const YES_NO: TarOption[] = [
  { value: '是', label: '是' },
  { value: '否', label: '否' },
]

const HAS_NONE: TarOption[] = [
  { value: '有', label: '有' },
  { value: '无', label: '无' },
]

export const TECH_AGREEMENT_STATUS = [
  { value: 'draft', label: '草稿' },
  { value: 'submitted', label: '已提交' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
] as const

export const TECH_AGREEMENT_SECTIONS: TarSection[] = [
  {
    key: 'basic',
    title: '基本信息',
    fields: [
      { key: 'applicant_id', label: '申请人', source: 'native', widget: 'person', required: true },
      { key: 'apply_at', label: '日期时间', source: 'native', widget: 'date', required: true },
      { key: 'owner_id', label: '业务员', source: 'native', widget: 'person', required: true },
      { key: 'department_id', label: '业务部门', source: 'native', widget: 'department', required: true },
      { key: 'company_name', label: '公司名称', source: 'native', widget: 'text', required: true },
      { key: 'industry', label: '所属行业', source: 'native', widget: 'text' },
      { key: 'address', label: '地址', source: 'native', widget: 'text' },
      {
        key: 'elec_ctrl', label: '电控装置', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '含电控电缆', label: '含电控电缆' },
          { value: '含电控不含电缆', label: '含电控不含电缆' },
          { value: '不含电控不含电缆', label: '不含电控不含电缆' },
          { value: '不含电控含电缆', label: '不含电控含电缆' },
        ],
      },
      { key: 'project_title', label: '项目名称及应用', source: 'native', widget: 'textarea', required: true },
      {
        key: 'has_weight_req', label: '是否有重量要求', source: 'native', widget: 'radio', required: true,
        options: HAS_NONE,
      },
      {
        key: 'use_idle_equip', label: '是否趁用呆滞设备', source: 'native', widget: 'radio', required: true,
        options: YES_NO,
      },
      {
        key: 'has_smart', label: '合同是否含智能化部分', source: 'native', widget: 'radio', required: true,
        options: YES_NO,
      },
      {
        key: 'need_pricing', label: '是否核价', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '已核价', label: '已核价' },
          { value: '未核价', label: '未核价' },
        ],
      },
      { key: 'sign_basis', label: '合同签订依据及情况', source: 'native', widget: 'text', required: true },
      { key: 'ref_contract_no', label: '参考合同号', source: 'native', widget: 'combo' },
      { key: 'pre_contact', label: '前期沟通人', source: 'native', widget: 'text', required: true },
    ],
    afterSlot: 'approve_files',
    fieldsAfterSlot: [
      { key: 'remark', label: '备注', source: 'native', widget: 'textarea' },
    ],
  },
  {
    key: 'approve_fill',
    title: '审批填写（总工/设计节点）',
    fillStage: 'approver',
    fields: [
      {
        key: 'design_approver_ids', label: '设计审批', source: 'form', widget: 'person_multi',
        fillStage: 'approver', required: true,
      },
      {
        key: 'design_approver_2_ids', label: '设计审批2', source: 'form', widget: 'person_multi',
        fillStage: 'approver', required: true,
      },
      {
        key: 'has_objection', label: '是否有异议', source: 'native', widget: 'radio',
        fillStage: 'approver', options: YES_NO,
      },
    ],
  },
]

export function tarSectionAllFields(sec: TarSection): TarFieldDef[] {
  return [...sec.fields, ...(sec.fieldsAfterSlot || [])]
}

export function tarInitiatorFields(): TarFieldDef[] {
  const out: TarFieldDef[] = []
  for (const sec of TECH_AGREEMENT_SECTIONS) {
    if (sec.fillStage === 'approver') continue
    for (const f of tarSectionAllFields(sec)) {
      if ((f.fillStage || 'initiator') === 'approver') continue
      out.push(f)
    }
  }
  return out
}

function isEmpty(v: unknown, widget?: TarWidget): boolean {
  if (v == null || v === '') return true
  if (Array.isArray(v) && v.length === 0) return true
  if (widget === 'person_multi' && Array.isArray(v) && v.length === 0) return true
  return false
}

/** 发起提交校验：仅校验发起人填写字段 */
export function findFirstMissingTarRequired(row: {
  form_json?: Record<string, unknown> | null
  [k: string]: unknown
}): { name: (string | number)[]; label: string } | null {
  const fj = (row.form_json || {}) as Record<string, unknown>
  for (const f of tarInitiatorFields()) {
    if (!f.required) continue
    const v = f.source === 'native' ? row[f.key] : fj[f.key]
    if (isEmpty(v, f.widget)) {
      return {
        name: f.source === 'native' ? [f.key] : ['form_json', f.key],
        label: f.label,
      }
    }
  }
  return null
}

export const TAR_NATIVE_KEYS = new Set([
  'applicant_id', 'applicant_name', 'apply_at',
  'owner_id', 'owner_name', 'department_id', 'department_name',
  'customer_id', 'company_name', 'industry', 'address', 'elec_ctrl',
  'project_title', 'has_weight_req', 'use_idle_equip', 'has_smart',
  'need_pricing', 'sign_basis', 'ref_contract_no', 'pre_contact',
  'remark', 'has_objection', 'status',
])

export const TAR_DATE_KEYS = new Set(['apply_at'])

export type TarListCellKind = 'text' | 'tag' | 'person' | 'dept' | 'date' | 'status'

export interface TarListColumnDef {
  key: string
  title: string
  width: number
  source: 'native' | 'form' | 'system'
  kind?: TarListCellKind
  nameKey?: string
  fixed?: 'left' | 'right'
}

/** 列表列对齐简道云 showFields */
export const TECH_AGREEMENT_LIST_COLUMNS: TarListColumnDef[] = [
  { key: 'review_code', title: '流水号', width: 168, source: 'native', fixed: 'left' },
  { key: 'applicant_id', title: '申请人', width: 100, source: 'native', kind: 'person', nameKey: 'applicant_name' },
  { key: 'apply_at', title: '日期时间', width: 160, source: 'native', kind: 'date' },
  { key: 'owner_id', title: '业务员', width: 100, source: 'native', kind: 'person', nameKey: 'owner_name' },
  { key: 'department_id', title: '业务部门', width: 160, source: 'native', kind: 'dept', nameKey: 'department_name' },
  { key: 'company_name', title: '公司名称', width: 220, source: 'native' },
  { key: 'industry', title: '所属行业', width: 120, source: 'native' },
  { key: 'address', title: '地址', width: 180, source: 'native' },
  { key: 'elec_ctrl', title: '电控装置', width: 150, source: 'native', kind: 'tag' },
  { key: 'project_title', title: '项目名称及应用', width: 200, source: 'native' },
  { key: 'has_weight_req', title: '是否有重量要求', width: 130, source: 'native', kind: 'tag' },
  { key: 'use_idle_equip', title: '是否趁用呆滞设备', width: 140, source: 'native', kind: 'tag' },
  { key: 'has_smart', title: '合同是否含智能化部分', width: 160, source: 'native', kind: 'tag' },
  { key: 'need_pricing', title: '是否核价', width: 100, source: 'native', kind: 'tag' },
  { key: 'sign_basis', title: '合同签订依据及情况', width: 180, source: 'native' },
  { key: 'ref_contract_no', title: '参考合同号', width: 140, source: 'native' },
  { key: 'pre_contact', title: '前期沟通人', width: 120, source: 'native' },
  { key: 'remark', title: '备注', width: 160, source: 'native' },
  { key: 'has_objection', title: '是否有异议', width: 110, source: 'native', kind: 'tag' },
  { key: 'created_by_name', title: '提交人', width: 100, source: 'system' },
  { key: 'created_at', title: '提交时间', width: 160, source: 'system', kind: 'date' },
  { key: 'updated_at', title: '更新时间', width: 160, source: 'system', kind: 'date' },
  // 贴右侧冻结，与操作列一并固定（操作列在列表页追加于其后）
  { key: 'status', title: '流程状态', width: 100, source: 'native', kind: 'status', fixed: 'right' },
]
