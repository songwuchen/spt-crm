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

export type ReviewAfterSlot = 'contacts' | 'review_files' | 'feedback_files'

export interface ReviewOption {
  value: string
  label: string
}

export interface ReviewShowWhen {
  field: string
  source?: ReviewFieldSource
  equals?: string[]
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
        key: 'review_type', label: '合同评审/项目评审', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '合同评审', label: '合同评审' },
          { value: '项目评审', label: '项目评审' },
        ],
      },
      {
        key: 'is_export', label: '是否出口合同', source: 'native', widget: 'radio', required: true,
        options: YES_NO,
      },
      {
        key: 'need_pricing', label: '是否核价', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '有核价', label: '有核价' },
          { value: '未核价', label: '未核价' },
        ],
      },
      {
        key: 'need_install', label: '是否需要安装', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '指导安装', label: '指导安装' },
          { value: '负责安装', label: '负责安装' },
          { value: '无需指导安装', label: '无需指导安装' },
        ],
      },
      { key: 'owner_name', label: '业务员', source: 'native', widget: 'text', required: true },
      { key: 'region_manager_name', label: '区域经理/组长', source: 'native', widget: 'text' },
      { key: 'department_name', label: '业务部门', source: 'native', widget: 'text' },
      { key: 'company_name', label: '公司名称', source: 'native', widget: 'text', required: true },
      {
        key: 'elec_ctrl', label: '电控装置', source: 'native', widget: 'radio',
        options: [
          { value: '含电控电缆', label: '含电控电缆' },
          { value: '含电控不含电缆', label: '含电控不含电缆' },
          { value: '不含电控不含电缆', label: '不含电控不含电缆' },
          { value: '不含电控含电缆', label: '不含电控含电缆' },
        ],
      },
    ],
  },
  {
    key: 'pricing',
    title: '核价信息',
    fields: [
      { key: 'pricing_no', label: '核价单号', source: 'reg', widget: 'text' },
      { key: 'cost_price', label: '成本价', source: 'reg', widget: 'textarea' },
      { key: 'motor_req', label: '核价配置要求的电机', source: 'reg', widget: 'text' },
      { key: 'bearing_req', label: '核价配置要求的轴承', source: 'reg', widget: 'text' },
      { key: 'material_req', label: '核价配置要求的主材材质', source: 'reg', widget: 'text' },
      { key: 'liner_req', label: '核价配置要求的衬板/筛板', source: 'reg', widget: 'text' },
      { key: 'special_req', label: '特殊要求', source: 'reg', widget: 'textarea' },
    ],
  },
  {
    key: 'customer',
    title: '客户信息',
    fields: [
      {
        key: 'customer_type', label: '客户类型', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '新客户', label: '新客户' },
          { value: '老客户', label: '老客户' },
        ],
      },
      { key: 'contract_copies', label: '正式合同份数', source: 'reg', widget: 'number' },
      { key: 'company_nature', label: '公司性质', source: 'reg', widget: 'text', required: true },
      { key: 'industry', label: '所属行业', source: 'reg', widget: 'text', required: true },
      { key: 'scale_fund', label: '规模及资金（万元）', source: 'reg', widget: 'number', required: true },
      { key: 'customer_relation', label: '客户关系', source: 'reg', widget: 'text', required: true },
      { key: 'dishonest_count', label: '失信信息', source: 'reg', widget: 'number' },
      { key: 'lawsuit_count', label: '诉讼纠纷', source: 'reg', widget: 'number' },
      { key: 'env_penalty_count', label: '环保处罚', source: 'reg', widget: 'number' },
      { key: 'tax_penalty_count', label: '税务处罚', source: 'reg', widget: 'number' },
      { key: 'other_penalty_count', label: '其它行政处罚', source: 'reg', widget: 'number' },
    ],
    afterSlot: 'contacts',
  },
  {
    key: 'project',
    title: '项目信息',
    fields: [
      { key: 'holding_desc', label: '母公司或控股公司的情况及性质说明', source: 'reg', widget: 'text', required: true },
      { key: 'project_title', label: '项目名称及应用', source: 'native', widget: 'textarea', required: true },
      { key: 'reported_at', label: '报备时间', source: 'native', widget: 'date' },
      { key: 'salary_insurance', label: '工资及保险情况', source: 'reg', widget: 'text', required: true },
      { key: 'contract_amount', label: '合同价格（元）', source: 'native', widget: 'money', required: true },
      { key: 'delivery_period', label: '交货期', source: 'native', widget: 'text' },
      {
        key: 'has_guarantee', label: '是否有保函', source: 'reg', widget: 'radio',
        options: YES_NO,
      },
      {
        key: 'guarantee_type', label: '保函类型', source: 'reg', widget: 'radio',
        options: [
          { value: '履约保函', label: '履约保函' },
          { value: '预付保函', label: '预付保函' },
          { value: '质量保函', label: '质量保函' },
        ],
        showWhen: { field: 'has_guarantee', source: 'reg', equals: ['是'] },
      },
      {
        key: 'has_weight_req', label: '是否有重量要求', source: 'reg', widget: 'radio',
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
        options: YES_NO,
      },
      { key: 'sign_basis', label: '合同签订依据及情况', source: 'reg', widget: 'text' },
      { key: 'ref_contract_no', label: '参考合同号', source: 'reg', widget: 'text' },
      { key: 'payment_method', label: '付款方式', source: 'reg', widget: 'text' },
      { key: 'company_survey', label: '公司现状调查', source: 'reg', widget: 'text' },
      { key: 'bid_status', label: '项目报备与投标情况', source: 'reg', widget: 'text' },
      { key: 'sales_supplement', label: '针对销售情况的补充', source: 'reg', widget: 'text' },
      { key: 'survey_req', label: '现场测绘及要求', source: 'reg', widget: 'text' },
    ],
    afterSlot: 'review_files',
  },
  {
    key: 'risk',
    title: '风险信息',
    fields: [
      { key: 'clause_opinion', label: '合同条款审核意见', source: 'reg', widget: 'textarea' },
      { key: 'legal_risk', label: '法务风险等级判断', source: 'reg', widget: 'radio', options: RISK },
      { key: 'legal_risk_desc', label: '法务风险等级文字描述', source: 'reg', widget: 'text' },
      { key: 'tech_risk', label: '技术风险等级判断', source: 'reg', widget: 'radio', options: RISK },
      { key: 'tech_risk_desc', label: '技术风险等级文字描述', source: 'reg', widget: 'text' },
      { key: 'biz_risk', label: '业务风险等级判断', source: 'reg', widget: 'radio', options: RISK },
      { key: 'biz_risk_desc', label: '业务风险等级文字描述', source: 'reg', widget: 'text' },
      { key: 'finance_risk', label: '财务风险等级判断', source: 'reg', widget: 'radio', options: RISK },
      { key: 'finance_risk_desc', label: '财务风险等级文字描述', source: 'reg', widget: 'text' },
      { key: 'purchase_risk', label: '采购风险等级判断', source: 'reg', widget: 'radio', options: RISK },
      { key: 'purchase_risk_desc', label: '采购风险等级文字描述', source: 'reg', widget: 'text' },
      { key: 'export_risk', label: '出口风险等级判断', source: 'reg', widget: 'radio', options: RISK },
      { key: 'export_risk_desc', label: '出口风险等级文字描述', source: 'reg', widget: 'text' },
      { key: 'credit_level', label: '重点数据及信用等级', source: 'reg', widget: 'text' },
      { key: 'past_biz_desc', label: '前期业务来往描述', source: 'reg', widget: 'text' },
      { key: 'pricing_supplement', label: '核价报价补充', source: 'reg', widget: 'text' },
    ],
  },
  {
    key: 'conclusion',
    title: '结论',
    fields: [
      { key: 'payment_term', label: '账期', source: 'native', widget: 'text' },
      { key: 'conclusion', label: '结论描述', source: 'native', widget: 'textarea' },
      {
        key: 'need_feedback', label: '是否反馈', source: 'reg', widget: 'radio',
        options: YES_NO,
      },
      { key: 'feedback_members', label: '成员多选（备注）', source: 'reg', widget: 'text' },
    ],
    afterSlot: 'feedback_files',
  },
  {
    key: 'signing',
    title: '合同签订',
    fields: [
      { key: 'drawing_no', label: '图纸编号', source: 'reg', widget: 'text' },
      { key: 'opinion_exec', label: '合同评审意见执行情况', source: 'reg', widget: 'textarea' },
    ],
  },
]

export function reviewSectionAllFields(sec: ReviewSection): ReviewFieldDef[] {
  return [...sec.fields, ...(sec.fieldsAfterSlot || [])]
}

export const REVIEW_NATIVE_KEYS = new Set([
  'review_type', 'is_export', 'need_pricing', 'need_install',
  'owner_name', 'region_manager_name', 'department_name', 'company_name',
  'elec_ctrl', 'customer_type', 'project_title', 'reported_at',
  'contract_amount', 'delivery_period', 'payment_term', 'conclusion',
  'owner_id', 'department_id', 'region_manager_id', 'customer_id', 'status',
])

export const REVIEW_DATE_KEYS = new Set(['reported_at'])
