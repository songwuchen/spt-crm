/** 简道云「合同评审」业务字段分区（CRM 创建/编辑/详情共用）

对齐 docs/product/_jdy_fields_pull_summary.md / _jdy_contract_review_fields.json。
不含：separator、linkfield/linkquery、已禁用小萌字段、辅助 ID。
native → 表顶层列；reg → review_json.*
*/

export type ReviewFieldSource = 'native' | 'reg'

export type ReviewWidget =
  | 'text'
  | 'textarea'
  | 'number'
  | 'money'
  | 'date'
  | 'radio'
  | 'select'
  | 'checkbox'
  | 'combo'         // 可输入可搜（对齐 JDY combo，如图纸编号）
  | 'person'        // 组织架构选人（对齐 JDY user）
  | 'person_multi'  // 多人（对齐 JDY usergroup）
  | 'department'    // 组织架构选部门（对齐 JDY dept）

export type ReviewAfterSlot = 'contacts' | 'pricing_files' | 'review_files' | 'feedback_files'

export interface ReviewOption {
  value: string
  label: string
}

export interface ReviewShowWhen {
  /** 单条件字段；仅用 allOf 时可省略 */
  field?: string
  source?: ReviewFieldSource
  equals?: string[]
  /** 全部满足才显示（与 field/equals 同时存在时一并 AND） */
  allOf?: ReviewShowWhen[]
}

export interface ReviewFieldDef {
  key: string
  label: string
  source: ReviewFieldSource
  widget?: ReviewWidget
  options?: ReviewOption[]
  showWhen?: ReviewShowWhen
  required?: boolean
  requiredWhen?: ReviewShowWhen
  /** 对齐简道云填写时机：
   * - initiator（默认）：创建/编辑可填
   * - approver：审批节点可填，创建不渲染
   * - display：表单禁用且无节点可写，仅详情只读展示
   */
  fillStage?: 'initiator' | 'approver' | 'display'
}

export interface ReviewSection {
  key: string
  title: string
  fields: ReviewFieldDef[]
  afterSlot?: ReviewAfterSlot
  fieldsAfterSlot?: ReviewFieldDef[]
}

const YES_NO: ReviewOption[] = [
  { value: '是', label: '是' },
  { value: '否', label: '否' },
]

const RISK: ReviewOption[] = [
  { value: '高', label: '高' },
  { value: '中', label: '中' },
  { value: '低', label: '低' },
]

/** 简道云 fieldShowRules 对照（docs/product/_tmp_cr_show_rules.json） */
const WHEN_CONTRACT: ReviewShowWhen = {
  field: 'review_type', source: 'native', equals: ['合同评审'],
}
const WHEN_PROJECT: ReviewShowWhen = {
  field: 'review_type', source: 'native', equals: ['项目评审'],
}
const WHEN_REVIEW_TYPE: ReviewShowWhen = {
  field: 'review_type', source: 'native', equals: ['合同评审', '项目评审'],
}
/** 简道云 rule5：是否外贸客户 = 否 → 显示客户关系 / 母公司说明 */
const WHEN_NOT_FOREIGN: ReviewShowWhen = {
  field: 'is_foreign_trade', source: 'reg', equals: ['否'],
}
const WHEN_EXPORT_YES: ReviewShowWhen = {
  field: 'is_export', source: 'native', equals: ['是'],
}
const WHEN_GUARANTEE_YES: ReviewShowWhen = {
  field: 'has_guarantee', source: 'reg', equals: ['是'],
}
/** 有核价明细：仅合同评审 + 是否核价=有核价（JDY rule4 仅控已取消的核价时间；CRM 明细按业务补） */
const WHEN_PRICING_DETAIL: ReviewShowWhen = {
  allOf: [
    WHEN_CONTRACT,
    { field: 'need_pricing', source: 'native', equals: ['有核价'] },
  ],
}
const RISK_NEED_DESC = ['高', '中']
function whenRiskDesc(riskKey: string, extra?: ReviewShowWhen): ReviewShowWhen {
  const riskCond: ReviewShowWhen = { field: riskKey, source: 'reg', equals: RISK_NEED_DESC }
  return { allOf: extra ? [extra, riskCond] : [WHEN_CONTRACT, riskCond] }
}

export const CONTRACT_REVIEW_STATUS = [
  { value: 'draft', label: '草稿' },
  { value: 'submitted', label: '已提交' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
] as const

export const CONTRACT_REVIEW_SECTIONS: ReviewSection[] = [
  {
    key: 'basic',
    title: '基本信息',
    fields: [
      {
        // 简道云：label「…（260518取消）」、description「项目评审由260518取消」→ 新建固定合同评审，不再提供切换
        key: 'review_type', label: '评审类型', source: 'native', widget: 'radio',
        options: [
          { value: '合同评审', label: '合同评审' },
          { value: '项目评审', label: '项目评审' }, // 仅历史详情只读展示
        ],
        fillStage: 'display',
      },
      {
        // rule1：仅合同评审
        key: 'is_export', label: '是否出口合同', source: 'native', widget: 'radio', required: true,
        options: YES_NO, showWhen: WHEN_CONTRACT,
      },
      {
        key: 'need_pricing', label: '是否核价', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '有核价', label: '有核价' },
          { value: '未核价', label: '未核价' },
        ],
        showWhen: WHEN_CONTRACT,
      },
      {
        key: 'need_install', label: '是否需要安装', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '指导安装', label: '指导安装' },
          { value: '负责安装', label: '负责安装' },
          { value: '无需指导安装', label: '无需指导安装' },
        ],
        showWhen: WHEN_CONTRACT,
      },
      // rule0：合同评审或项目评审
      { key: 'owner_id', label: '业务员', source: 'native', widget: 'person', required: true, showWhen: WHEN_REVIEW_TYPE },
      { key: 'region_manager_id', label: '区域经理/组长', source: 'native', widget: 'person', showWhen: WHEN_CONTRACT },
      { key: 'department_id', label: '业务部门', source: 'native', widget: 'department', showWhen: WHEN_REVIEW_TYPE },
      { key: 'company_name', label: '公司名称', source: 'native', widget: 'text', required: true, showWhen: WHEN_REVIEW_TYPE },
      {
        // 触发 rule5；客户回填为「是/否」文本
        key: 'is_foreign_trade', label: '是否外贸客户', source: 'reg', widget: 'radio',
        options: YES_NO, showWhen: WHEN_REVIEW_TYPE,
      },
      {
        key: 'elec_ctrl', label: '电控装置', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '含电控电缆', label: '含电控电缆' },
          { value: '含电控不含电缆', label: '含电控不含电缆' },
          { value: '不含电控不含电缆', label: '不含电控不含电缆' },
          { value: '不含电控含电缆', label: '不含电控含电缆' },
        ],
        showWhen: WHEN_CONTRACT,
      },
    ],
  },
  {
    key: 'pricing',
    title: '核价信息',
    fields: [
      {
        key: 'pricing_no', label: '核价单号', source: 'reg', widget: 'text',
        showWhen: WHEN_PRICING_DETAIL,
      },
      {
        key: 'cost_price', label: '成本价', source: 'reg', widget: 'textarea',
        showWhen: WHEN_PRICING_DETAIL,
      },
      {
        key: 'motor_req', label: '核价配置要求的电机', source: 'reg', widget: 'text',
        showWhen: WHEN_PRICING_DETAIL,
      },
      {
        key: 'bearing_req', label: '核价配置要求的轴承', source: 'reg', widget: 'text',
        showWhen: WHEN_PRICING_DETAIL,
      },
      {
        key: 'material_req', label: '核价配置要求的主材材质', source: 'reg', widget: 'text',
        showWhen: WHEN_PRICING_DETAIL,
      },
      {
        key: 'liner_req', label: '核价配置要求的衬板/筛板', source: 'reg', widget: 'text',
        showWhen: WHEN_PRICING_DETAIL,
      },
      {
        key: 'special_req', label: '特殊要求', source: 'reg', widget: 'textarea',
        showWhen: WHEN_PRICING_DETAIL,
      },
    ],
    afterSlot: 'pricing_files',
  },
  {
    key: 'customer',
    title: '客户信息',
    fields: [
      {
        key: 'customer_type', label: '客户类型', source: 'native', widget: 'radio',
        options: [
          { value: '新客户', label: '新客户' },
          { value: '老客户', label: '老客户' },
        ],
        showWhen: WHEN_REVIEW_TYPE,
      },
      { key: 'contract_copies', label: '正式合同份数', source: 'reg', widget: 'number', showWhen: WHEN_CONTRACT },
      {
        key: 'company_nature', label: '公司性质', source: 'reg', widget: 'text', required: true,
        showWhen: WHEN_REVIEW_TYPE,
      },
      {
        key: 'industry', label: '所属行业', source: 'reg', widget: 'text', required: true,
        showWhen: WHEN_REVIEW_TYPE,
      },
      {
        key: 'scale_fund', label: '规模及资金（万元）', source: 'reg', widget: 'number', required: true,
        showWhen: WHEN_REVIEW_TYPE,
      },
      // rule5：外贸=否 时显示并必填
      {
        key: 'customer_relation', label: '客户关系', source: 'reg', widget: 'text',
        showWhen: WHEN_NOT_FOREIGN, requiredWhen: WHEN_NOT_FOREIGN,
      },
      { key: 'dishonest_count', label: '失信信息', source: 'reg', widget: 'number', showWhen: WHEN_CONTRACT },
      { key: 'lawsuit_count', label: '诉讼纠纷', source: 'reg', widget: 'number', showWhen: WHEN_CONTRACT },
      { key: 'env_penalty_count', label: '环保处罚', source: 'reg', widget: 'number', showWhen: WHEN_CONTRACT },
      { key: 'tax_penalty_count', label: '税务处罚', source: 'reg', widget: 'number', showWhen: WHEN_CONTRACT },
      { key: 'other_penalty_count', label: '其它行政处罚', source: 'reg', widget: 'number', showWhen: WHEN_CONTRACT },
    ],
    afterSlot: 'contacts',
  },
  {
    key: 'project',
    title: '项目信息',
    fields: [
      {
        key: 'holding_desc', label: '母公司或控股公司的情况及性质说明', source: 'reg', widget: 'text',
        showWhen: WHEN_NOT_FOREIGN, requiredWhen: WHEN_NOT_FOREIGN,
      },
      { key: 'project_title', label: '项目名称及应用', source: 'native', widget: 'textarea' },
      // rule2：历史「仅项目评审」；260518 后新建不再出现
      {
        key: 'reported_at', label: '报备时间', source: 'native', widget: 'date',
        showWhen: WHEN_PROJECT, fillStage: 'display',
      },
      {
        key: 'salary_insurance', label: '工资及保险情况', source: 'reg', widget: 'text', required: true,
        showWhen: WHEN_CONTRACT,
      },
      { key: 'contract_amount', label: '合同价格（元）', source: 'native', widget: 'money', showWhen: WHEN_CONTRACT },
      { key: 'delivery_period', label: '交货期', source: 'native', widget: 'text' },
      {
        key: 'has_guarantee', label: '是否有保函', source: 'reg', widget: 'radio',
        options: YES_NO,
      },
      {
        // rule3
        key: 'guarantee_type', label: '保函类型', source: 'reg', widget: 'radio',
        options: [
          { value: '履约保函', label: '履约保函' },
          { value: '预付保函', label: '预付保函' },
          { value: '质量保函', label: '质量保函' },
        ],
        showWhen: WHEN_GUARANTEE_YES,
      },
      {
        key: 'has_weight_req', label: '是否有重量要求', source: 'reg', widget: 'radio', required: true,
        options: [
          { value: '有', label: '有' },
          { value: '无', label: '无' },
        ],
      },
      {
        key: 'use_idle_equip', label: '是否趁用呆滞设备', source: 'reg', widget: 'radio',
        options: YES_NO,
      },
      {
        key: 'has_smart', label: '合同是否含智能化部分', source: 'reg', widget: 'radio',
        options: YES_NO, showWhen: WHEN_CONTRACT,
      },
      {
        key: 'sign_basis', label: '合同签订依据及情况', source: 'reg', widget: 'text', required: true,
        showWhen: WHEN_CONTRACT,
      },
      { key: 'ref_contract_no', label: '参考合同号', source: 'reg', widget: 'text', showWhen: WHEN_CONTRACT },
      { key: 'payment_method', label: '付款方式', source: 'reg', widget: 'text' },
      { key: 'company_survey', label: '公司现状调查', source: 'reg', widget: 'text' },
      { key: 'bid_status', label: '项目报备与投标情况', source: 'reg', widget: 'text' },
      { key: 'sales_supplement', label: '针对销售情况的补充', source: 'reg', widget: 'text' },
      { key: 'survey_req', label: '现场测绘及要求', source: 'reg', widget: 'text', showWhen: WHEN_REVIEW_TYPE },
    ],
    afterSlot: 'review_files',
  },
  {
    key: 'risk',
    title: '风险信息',
    fields: [
      // 审批填写；rule1 仅合同评审展示风险区（详情/审批侧）
      {
        key: 'clause_opinion', label: '合同条款审核意见', source: 'reg', widget: 'textarea',
        fillStage: 'approver', showWhen: WHEN_CONTRACT,
      },
      {
        key: 'legal_risk', label: '法务风险等级判断', source: 'reg', widget: 'radio', options: RISK,
        fillStage: 'approver', showWhen: WHEN_CONTRACT,
      },
      {
        key: 'legal_risk_desc', label: '法务风险等级文字描述', source: 'reg', widget: 'text',
        fillStage: 'approver',
        showWhen: whenRiskDesc('legal_risk'),
      },
      {
        key: 'tech_risk', label: '技术风险等级判断', source: 'reg', widget: 'radio', options: RISK,
        fillStage: 'approver', showWhen: WHEN_CONTRACT,
      },
      {
        key: 'tech_risk_desc', label: '技术风险等级文字描述', source: 'reg', widget: 'text',
        fillStage: 'approver',
        showWhen: whenRiskDesc('tech_risk'),
      },
      {
        key: 'biz_risk', label: '业务风险等级判断', source: 'reg', widget: 'radio', options: RISK,
        fillStage: 'approver', showWhen: WHEN_CONTRACT,
      },
      {
        key: 'biz_risk_desc', label: '业务风险等级文字描述', source: 'reg', widget: 'text',
        fillStage: 'approver',
        showWhen: whenRiskDesc('biz_risk'),
      },
      {
        key: 'finance_risk', label: '财务风险等级判断', source: 'reg', widget: 'radio', options: RISK,
        fillStage: 'approver', showWhen: WHEN_CONTRACT,
      },
      {
        key: 'finance_risk_desc', label: '财务风险等级文字描述', source: 'reg', widget: 'text',
        fillStage: 'approver',
        showWhen: whenRiskDesc('finance_risk'),
      },
      {
        key: 'purchase_risk', label: '采购风险等级判断', source: 'reg', widget: 'radio', options: RISK,
        fillStage: 'approver', showWhen: WHEN_CONTRACT,
      },
      {
        key: 'purchase_risk_desc', label: '采购风险等级文字描述', source: 'reg', widget: 'text',
        fillStage: 'approver',
        showWhen: whenRiskDesc('purchase_risk'),
      },
      // rule18：出口=是 才显示出口风险
      {
        key: 'export_risk', label: '出口风险等级判断', source: 'reg', widget: 'radio', options: RISK,
        fillStage: 'approver', showWhen: WHEN_EXPORT_YES,
      },
      {
        key: 'export_risk_desc', label: '出口风险等级文字描述', source: 'reg', widget: 'text',
        fillStage: 'approver',
        showWhen: whenRiskDesc('export_risk', WHEN_EXPORT_YES),
      },
      {
        // 简道云：visible/enable=false，发起与各审批节点均不可写 → 仅详情只读
        key: 'credit_level', label: '重点数据及信用等级', source: 'reg', widget: 'text',
        fillStage: 'display',
      },
      {
        key: 'past_biz_desc', label: '前期业务来往描述', source: 'reg', widget: 'text',
        fillStage: 'display',
      },
      {
        key: 'pricing_supplement', label: '核价报价补充', source: 'reg', widget: 'text',
        fillStage: 'display',
      },
    ],
  },
  {
    key: 'conclusion',
    title: '结论',
    fields: [
      {
        key: 'payment_term', label: '账期', source: 'native', widget: 'text',
        fillStage: 'approver', showWhen: WHEN_CONTRACT,
      },
      { key: 'conclusion', label: '结论描述', source: 'native', widget: 'textarea', fillStage: 'approver' },
      {
        key: 'need_feedback', label: '是否反馈', source: 'reg', widget: 'radio',
        options: YES_NO, fillStage: 'approver',
      },
      { key: 'feedback_members', label: '成员多选', source: 'reg', widget: 'person_multi', fillStage: 'approver' },
    ],
    afterSlot: 'feedback_files',
  },
  {
    key: 'signing',
    title: '合同签订',
    fields: [
      { key: 'drawing_no', label: '图纸编号', source: 'reg', widget: 'combo', fillStage: 'approver' },
      { key: 'opinion_exec', label: '合同评审意见执行情况', source: 'reg', widget: 'textarea', fillStage: 'approver' },
    ],
  },
]

export function reviewSectionAllFields(sec: ReviewSection): ReviewFieldDef[] {
  return [...sec.fields, ...(sec.fieldsAfterSlot || [])]
}

/** 取字段当前值（native 顶层 / reg → review_json） */
export function readReviewFieldValue(
  row: Record<string, unknown>,
  field: ReviewFieldDef,
): unknown {
  if (field.source === 'native') return row[field.key]
  const rj = (row.review_json || {}) as Record<string, unknown>
  return rj[field.key]
}

export function reviewDepVisible(
  dep: ReviewShowWhen | undefined,
  row: Record<string, unknown>,
): boolean {
  if (!dep) return true
  if (dep.allOf?.length) {
    if (!dep.allOf.every((d) => reviewDepVisible(d, row))) return false
  }
  if (!dep.field) return true
  const v = dep.source === 'native'
    ? row[dep.field]
    : ((row.review_json || {}) as Record<string, unknown>)[dep.field]
  if (dep.equals?.length) {
    return dep.equals.includes(v == null ? '' : String(v))
  }
  return v != null && v !== ''
}

function isEmptyReviewValue(v: unknown, widget?: ReviewWidget): boolean {
  if (v == null || v === '') return true
  if ((widget === 'checkbox' || widget === 'person_multi') && Array.isArray(v) && v.length === 0) return true
  return false
}

/**
 * 找出第一条未填的必填项（含 requiredWhen），用于提交前拦截并滚到编辑页对应字段。
 * 返回 Form name path + 中文标签。
 */
export function findFirstMissingReviewRequired(
  row: Record<string, unknown>,
): { name: (string | number)[]; label: string } | null {
  for (const sec of CONTRACT_REVIEW_SECTIONS) {
    for (const f of reviewSectionAllFields(sec)) {
      if (f.fillStage === 'approver' || f.fillStage === 'display') continue
      if (!reviewDepVisible(f.showWhen, row)) continue
      const need = f.required || (f.requiredWhen ? reviewDepVisible(f.requiredWhen, row) : false)
      if (!need) continue
      const v = readReviewFieldValue(row, f)
      if (isEmptyReviewValue(v, f.widget)) {
        return {
          name: f.source === 'native' ? [f.key] : ['review_json', f.key],
          label: f.label,
        }
      }
    }
  }
  return null
}

export const REVIEW_NATIVE_KEYS = new Set([
  'review_type', 'is_export', 'need_pricing', 'need_install',
  'owner_id', 'owner_name', 'region_manager_id', 'region_manager_name',
  'department_id', 'department_name', 'company_name',
  'elec_ctrl', 'customer_type', 'project_title', 'reported_at',
  'contract_amount', 'delivery_period', 'payment_term', 'conclusion',
  'customer_id', 'status',
])

export const REVIEW_DATE_KEYS = new Set(['reported_at'])

/** 列表单元格渲染类型（对齐简道云数据管理：选项 Tag、人员蓝字） */
export type ReviewListCellKind =
  | 'text'
  | 'tag'
  | 'money'
  | 'person'
  | 'dept'
  | 'date'
  | 'number'
  | 'status'

/**
 * 合同评审列表列 — 顺序/文案对齐简道云 attr.showFields
 *（docs/product/_jdy_contract_review_edit_raw.json）。
 * 跳过：辅助 ID、已取消字段、附件/图片、联系人子表展开列。
 * defaultHidden=true 的长文/审批描述默认折叠，可在「列配置」调出。
 */
export interface ReviewListColumnDef {
  key: string
  title: string
  width: number
  source: 'native' | 'reg' | 'system'
  kind?: ReviewListCellKind
  /** person/dept 时用于显示的名称列（native） */
  nameKey?: string
  defaultHidden?: boolean
  fixed?: 'left' | 'right'
}

export const CONTRACT_REVIEW_LIST_COLUMNS: ReviewListColumnDef[] = [
  { key: 'review_code', title: '流水号', width: 150, source: 'native', fixed: 'left' },
  { key: 'review_type', title: '评审类型', width: 110, source: 'native', kind: 'tag' },
  { key: 'is_export', title: '是否出口合同', width: 120, source: 'native', kind: 'tag' },
  { key: 'need_pricing', title: '是否核价', width: 120, source: 'native', kind: 'tag' },
  { key: 'need_install', title: '是否需要安装', width: 140, source: 'native', kind: 'tag' },
  { key: 'owner_id', title: '业务员', width: 100, source: 'native', kind: 'person', nameKey: 'owner_name' },
  { key: 'region_manager_id', title: '区域经理/组长', width: 120, source: 'native', kind: 'person', nameKey: 'region_manager_name' },
  { key: 'department_id', title: '业务部门', width: 160, source: 'native', kind: 'dept', nameKey: 'department_name' },
  { key: 'company_name', title: '公司名称', width: 220, source: 'native' },
  { key: 'is_foreign_trade', title: '是否外贸客户', width: 120, source: 'reg' },
  { key: 'elec_ctrl', title: '电控装置', width: 150, source: 'native', kind: 'tag' },
  { key: 'pricing_no', title: '核价单号', width: 140, source: 'reg' },
  { key: 'cost_price', title: '成本价', width: 140, source: 'reg', defaultHidden: true },
  { key: 'motor_req', title: '核价配置要求的电机', width: 150, source: 'reg', defaultHidden: true },
  { key: 'bearing_req', title: '核价配置要求的轴承', width: 150, source: 'reg', defaultHidden: true },
  { key: 'material_req', title: '核价配置要求的主材材质', width: 160, source: 'reg', defaultHidden: true },
  { key: 'liner_req', title: '核价配置要求的衬板/筛板', width: 160, source: 'reg', defaultHidden: true },
  { key: 'special_req', title: '特殊要求', width: 160, source: 'reg', defaultHidden: true },
  { key: 'customer_type', title: '客户类型', width: 100, source: 'native', kind: 'tag' },
  { key: 'contract_copies', title: '正式合同份数', width: 120, source: 'reg', kind: 'number' },
  { key: 'company_nature', title: '公司性质', width: 120, source: 'reg' },
  { key: 'industry', title: '所属行业', width: 120, source: 'reg' },
  { key: 'scale_fund', title: '规模及资金（万元）', width: 140, source: 'reg', kind: 'number' },
  { key: 'customer_relation', title: '客户关系', width: 120, source: 'reg' },
  { key: 'dishonest_count', title: '失信信息', width: 100, source: 'reg', kind: 'number' },
  { key: 'lawsuit_count', title: '诉讼纠纷', width: 100, source: 'reg', kind: 'number' },
  { key: 'env_penalty_count', title: '环保处罚', width: 100, source: 'reg', kind: 'number' },
  { key: 'tax_penalty_count', title: '税务处罚', width: 100, source: 'reg', kind: 'number' },
  { key: 'other_penalty_count', title: '其它行政处罚', width: 120, source: 'reg', kind: 'number' },
  { key: 'holding_desc', title: '母公司或控股公司的情况及性质说明', width: 200, source: 'reg', defaultHidden: true },
  { key: 'project_title', title: '项目名称及应用', width: 200, source: 'native' },
  { key: 'reported_at', title: '报备时间', width: 120, source: 'native', kind: 'date' },
  { key: 'salary_insurance', title: '工资及保险情况', width: 140, source: 'reg', defaultHidden: true },
  { key: 'contract_amount', title: '合同价格（元）', width: 130, source: 'native', kind: 'money' },
  { key: 'delivery_period', title: '交货期', width: 120, source: 'native' },
  { key: 'has_guarantee', title: '是否有保函', width: 110, source: 'reg', kind: 'tag' },
  { key: 'guarantee_type', title: '保函类型', width: 110, source: 'reg', kind: 'tag' },
  { key: 'has_weight_req', title: '是否有重量要求', width: 130, source: 'reg', kind: 'tag' },
  { key: 'use_idle_equip', title: '是否趁用呆滞设备', width: 140, source: 'reg', kind: 'tag' },
  { key: 'has_smart', title: '合同是否含智能化部分', width: 160, source: 'reg', kind: 'tag' },
  { key: 'sign_basis', title: '合同签订依据及情况', width: 160, source: 'reg', defaultHidden: true },
  { key: 'ref_contract_no', title: '参考合同号', width: 130, source: 'reg' },
  { key: 'payment_method', title: '付款方式', width: 140, source: 'reg' },
  { key: 'company_survey', title: '公司现状调查', width: 140, source: 'reg', defaultHidden: true },
  { key: 'bid_status', title: '项目报备与投标情况', width: 150, source: 'reg', defaultHidden: true },
  { key: 'sales_supplement', title: '针对销售情况的补充', width: 150, source: 'reg', defaultHidden: true },
  { key: 'survey_req', title: '现场测绘及要求', width: 140, source: 'reg', defaultHidden: true },
  { key: 'clause_opinion', title: '合同条款审核意见', width: 180, source: 'reg', defaultHidden: true },
  { key: 'legal_risk', title: '法务风险等级判断', width: 140, source: 'reg', kind: 'tag' },
  { key: 'legal_risk_desc', title: '法务风险等级文字描述', width: 160, source: 'reg', defaultHidden: true },
  { key: 'tech_risk', title: '技术风险等级判断', width: 140, source: 'reg', kind: 'tag' },
  { key: 'tech_risk_desc', title: '技术风险等级文字描述', width: 160, source: 'reg', defaultHidden: true },
  { key: 'biz_risk', title: '业务风险等级判断', width: 140, source: 'reg', kind: 'tag' },
  { key: 'biz_risk_desc', title: '业务风险等级文字描述', width: 160, source: 'reg', defaultHidden: true },
  { key: 'finance_risk', title: '财务风险等级判断', width: 140, source: 'reg', kind: 'tag' },
  { key: 'finance_risk_desc', title: '财务风险等级文字描述', width: 160, source: 'reg', defaultHidden: true },
  { key: 'purchase_risk', title: '采购风险等级判断', width: 140, source: 'reg', kind: 'tag' },
  { key: 'purchase_risk_desc', title: '采购风险等级文字描述', width: 160, source: 'reg', defaultHidden: true },
  { key: 'export_risk', title: '出口风险等级判断', width: 140, source: 'reg', kind: 'tag' },
  { key: 'export_risk_desc', title: '出口风险等级文字描述', width: 160, source: 'reg', defaultHidden: true },
  { key: 'credit_level', title: '重点数据及信用等级', width: 150, source: 'reg', defaultHidden: true },
  { key: 'past_biz_desc', title: '前期业务来往描述', width: 150, source: 'reg', defaultHidden: true },
  { key: 'pricing_supplement', title: '核价报价补充', width: 140, source: 'reg', defaultHidden: true },
  { key: 'payment_term', title: '账期', width: 100, source: 'native' },
  { key: 'conclusion', title: '结论描述', width: 180, source: 'native', defaultHidden: true },
  { key: 'need_feedback', title: '是否反馈', width: 100, source: 'reg', kind: 'tag' },
  { key: 'drawing_no', title: '图纸编号', width: 140, source: 'reg' },
  { key: 'opinion_exec', title: '合同评审意见执行情况', width: 180, source: 'reg', defaultHidden: true },
  { key: 'created_by_name', title: '提交人', width: 90, source: 'system' },
  { key: 'created_at', title: '创建时间', width: 120, source: 'system', kind: 'date' },
  { key: 'updated_at', title: '更新时间', width: 120, source: 'system', kind: 'date', defaultHidden: true },
  // 贴右侧冻结，与操作列一并固定（操作列在列表页追加于其后）
  { key: 'status', title: '流程状态', width: 100, source: 'native', kind: 'status', fixed: 'right' },
]
