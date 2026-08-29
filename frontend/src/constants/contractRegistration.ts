/** 简道云「合同登记表」业务字段分区（CRM 创建/编辑/详情共用）

字段顺序严格对齐 live schema（_jdy_fields_pull_summary.md）。
附件槽位用 afterSlot 对齐简道云 upload/image（走 CRM Attachment，按 biz_type 分类）。
不含：separator、linkfield/linkquery/lookup、防重辅助列。

必填：简道云 fields API 经 wrapper 未返回 allowBlank；以下按登记业务硬必填 + 条件必填配置。
*/
export type RegFieldSource = 'native' | 'reg'

/** 与简道云 widget 对应的录入控件 */
export type RegWidget =
  | 'text'
  | 'textarea'
  | 'number'
  | 'money'
  | 'date'
  | 'radio'       // radiogroup
  | 'select'      // combo
  | 'checkbox'    // checkboxgroup / combocheck → 多选
  | 'person'      // 组织架构选人
  | 'department'  // 组织架构选部门
  | 'customer'    // 客户管理选择器
  | 'project'     // 商机选择器

export type RegAfterSlot =
  | 'line_items'
  | 'payment_terms'
  | 'contract_files'      // 附件/图片/验收单（其他信息后）
  | 'accept_files'        // 验收资料上传

/** 简道云附件槽 → CRM AttachmentLink.biz_type（biz_id=合同 id） */
export const CONTRACT_ATTACHMENT_SLOTS = [
  { key: 'contract_files', bizType: 'contract_agreement', title: '附件（合同、协议）', accept: undefined as string | undefined },
  { key: 'contract_files', bizType: 'contract_image', title: '图片（合同、协议）', accept: 'image/*' },
  { key: 'contract_files', bizType: 'contract_acceptance', title: '验收单', accept: undefined as string | undefined },
  { key: 'accept_files', bizType: 'contract_accept_docs', title: '验收资料上传', accept: undefined as string | undefined },
] as const

export interface RegOption {
  value: string
  label: string
}

export interface RegShowWhen {
  /** 依赖字段 key（native 顶层或 registration_json 内） */
  field: string
  source?: RegFieldSource
  /** 等于任一值时显示；未配置则只要有值就显示 */
  equals?: string[]
}

export interface RegFieldDef {
  key: string
  label: string
  source: RegFieldSource
  widget?: RegWidget
  options?: RegOption[]
  /**
   * 本地兜底显隐（策略未加载/失败时用）。
   * 产品规则已迁到后端 SYSTEM_RULES["contract"]，经 FieldPolicy 求值；
   * 已编目字段优先走策略，勿只改这里。
   */
  showWhen?: RegShowWhen
  /** 始终必填 */
  required?: boolean
  /**
   * 条件必填兜底；已编目字段以 SYSTEM_RULES required 为准。
   */
  requiredWhen?: RegShowWhen
  /**
   * 是否在创建/编辑填报页展示；false = 仅审批节点填写（对齐 catalog available_on_create）。
   * 缺省 true。策略已加载时以 catalog 为准。
   */
  availableOnCreate?: boolean
  /** 只读展示（如系统自动生成的图纸编号） */
  readOnly?: boolean
  placeholder?: string
  /** 选项来自低代码基础表（ensureBuiltin code），异步 lookup */
  lookupFormCode?: 'application_field' | 'application_material' | 'material_name'
}

export interface RegSection {
  key: string
  title: string
  fields: RegFieldDef[]
  /** 插在 fields 与 fieldsAfterSlot 之间（对齐简道云 subform / 附件位置） */
  afterSlot?: RegAfterSlot
  fieldsAfterSlot?: RegFieldDef[]
}

const YES_NO: RegOption[] = [
  { value: '是', label: '是' },
  { value: '否', label: '否' },
]

/** 分区内全部字段（含 afterSlot 后半段） */
export function sectionAllFields(sec: RegSection): RegFieldDef[] {
  return [...sec.fields, ...(sec.fieldsAfterSlot || [])]
}

export const CONTRACT_REGISTRATION_SECTIONS: RegSection[] = [
  // —— 表头（简道云无 separator，自下卡日期起）——
  {
    key: 'header',
    title: '基本信息',
    fields: [
      { key: 'serial_no', label: '流水号', source: 'native', widget: 'text', readOnly: true, placeholder: '保存后自动生成' },
      { key: 'project_id', label: '关联商机', source: 'native', widget: 'project' },
      { key: 'customer_id', label: '关联客户', source: 'native', widget: 'customer', required: true },
      { key: 'card_date', label: '下卡日期', source: 'native', widget: 'date', required: true },
      { key: 'customer_code', label: '客户编号', source: 'reg', widget: 'text' },
      { key: 'department_id', label: '部门', source: 'native', widget: 'department', required: true },
      { key: 'assignee_id', label: '业务人员', source: 'native', widget: 'person', required: true },
      {
        key: 'change_type', label: '合同状态', source: 'native', widget: 'radio', required: true,
        options: [
          { value: 'new', label: '新增' },
          { value: 'change', label: '变动' },
        ],
      },
      {
        key: 'change_reason', label: '变动原因', source: 'reg', widget: 'text',
        showWhen: { field: 'change_type', source: 'native', equals: ['change', '变动'] },
        requiredWhen: { field: 'change_type', source: 'native', equals: ['change', '变动'] },
      },
      {
        key: 'acquire_method', label: '合同获取信息方式', source: 'native', widget: 'radio', required: true,
        options: [
          { value: '公开招标', label: '公开招标' },
          { value: '邀请招标', label: '邀请招标' },
          { value: '协商一致', label: '协商一致' },
        ],
      },
      { key: 'review_sn', label: '合同/项目评审流水号', source: 'reg', widget: 'text' },
      { key: 'review_sn_xm', label: '小萌合同评审流水号', source: 'reg', widget: 'text' },
      { key: 'factory_no', label: '出厂编号', source: 'reg', widget: 'text' },
    ],
  },
  // —— 合同产品信息（明细子表插在采购员/质检员之后、合同总金额之前）——
  {
    key: 'product',
    title: '合同产品信息',
    fields: [
      { key: 'order_date', label: '订货日期', source: 'native', widget: 'date', required: true },
      {
        // 简道云：财务审核节点填写（创建/编辑填报页不展示）
        key: 'contract_type', label: '合同类型', source: 'reg', widget: 'radio',
        availableOnCreate: false,
        options: [
          { value: '正式', label: '正式' },
          { value: '非正式', label: '非正式' },
        ],
      },
      {
        key: 'contract_no', label: '合同号', source: 'native', widget: 'text', required: true,
        readOnly: true,
        placeholder: '选自合同图纸对应表的合同号',
      },
      {
        key: 'drawing_no', label: '图纸编号', source: 'native', widget: 'text',
        required: true,
        availableOnCreate: true,
        placeholder: '从合同图纸对应表选择',
      },
      { key: 'project_name', label: '项目名称', source: 'reg', widget: 'text', required: true },
      { key: 'peer_contract_no', label: '对方合同号', source: 'native', widget: 'text', required: true },
      { key: 'tax_included', label: '是否含税', source: 'reg', widget: 'radio', options: YES_NO, required: true },
      { key: 'is_export', label: '设备是否出口', source: 'reg', widget: 'radio', options: YES_NO, required: true },
      {
        key: 'need_install', label: '是否需要安装', source: 'reg', widget: 'radio', required: true,
        options: [
          { value: '不需要安装', label: '不需要安装' },
          { value: '指导安装', label: '指导安装' },
          { value: '现场安装', label: '现场安装' },
          { value: '拆旧装新', label: '拆旧装新' },
        ],
      },
      { key: 'info_complete', label: '信息是否齐全', source: 'reg', widget: 'radio', options: YES_NO, required: true },
      {
        key: 'missing_items', label: '缺少项', source: 'reg', widget: 'checkbox',
        options: [
          { value: '联系人', label: '联系人' },
          { value: '联系方式', label: '联系方式' },
          { value: '邮箱', label: '邮箱' },
          { value: '地址', label: '地址' },
        ],
        showWhen: { field: 'info_complete', source: 'reg', equals: ['否'] },
        requiredWhen: { field: 'info_complete', source: 'reg', equals: ['否'] },
      },
      {
        key: 'info_incomplete_note', label: '信息不齐全备注', source: 'reg', widget: 'textarea',
        showWhen: { field: 'info_complete', source: 'reg', equals: ['否'] },
      },
      {
        // 对齐简道云：始终可见、allowBlank=true，无 fieldShowRules / 条件必填
        key: 'export_type', label: '出口类型', source: 'reg', widget: 'text',
        placeholder: '如：FOB,CIF,CFR',
      },
      {
        key: 'contract_form', label: '合同形式', source: 'reg', widget: 'radio', required: true,
        options: [
          { value: '正式合同', label: '正式合同' },
          { value: '非正式合同', label: '非正式合同' },
          { value: '年标合同，订单无章', label: '年标合同，订单无章' },
          { value: '年标合同，订单有章', label: '年标合同，订单有章' },
          { value: '抖店', label: '抖店' },
        ],
      },
      { key: 'standard_delivery', label: '是否标准交付', source: 'reg', widget: 'radio', options: YES_NO, required: true },
      {
        key: 'delivery_mode', label: '方式', source: 'reg', widget: 'radio',
        options: [
          { value: 'YZO', label: 'YZO' },
          { value: 'YZS', label: 'YZS' },
          { value: 'YZO和YZS', label: 'YZO和YZS' },
        ],
        // 对齐简道云 fieldShowRules：是否标准交付=是 → 显示「方式」
        showWhen: { field: 'standard_delivery', source: 'reg', equals: ['是'] },
        requiredWhen: { field: 'standard_delivery', source: 'reg', equals: ['是'] },
      },
      { key: 'is_rotary_sieve', label: '是否为旋振筛', source: 'reg', widget: 'radio', options: YES_NO, required: true },
      {
        key: 'fill_code', label: '填写代码', source: 'reg', widget: 'text',
        showWhen: { field: 'is_rotary_sieve', source: 'reg', equals: ['是'] },
      },
      { key: 'purchasers', label: '采购员', source: 'reg', widget: 'text' },
      { key: 'inspectors', label: '质检员', source: 'reg', widget: 'text' },
    ],
    afterSlot: 'line_items',
    fieldsAfterSlot: [
      { key: 'amount_total', label: '合同总金额', source: 'native', widget: 'money', required: true },
      { key: 'tech_requirements', label: '技术参数及要求', source: 'reg', widget: 'textarea' },
      { key: 'packaging', label: '包装情况', source: 'reg', widget: 'text' },
      {
        key: 'paint_req', label: '油漆要求', source: 'reg', widget: 'radio', required: true,
        options: [
          { value: '有协议指定要求', label: '有协议指定要求' },
          { value: '待定', label: '待定' },
          { value: '企标', label: '企标' },
          { value: '参考某合同，请在备注填写所参考的合同号', label: '参考某合同，请在备注填写所参考的合同号' },
          { value: '其他', label: '其他' },
        ],
      },
      {
        key: 'workload', label: '工作量', source: 'reg', widget: 'radio', required: true,
        options: [
          { value: '设备', label: '设备' },
          { value: '备件', label: '备件' },
          { value: '电机', label: '电机' },
          { value: '出口', label: '出口' },
        ],
      },
    ],
  },
  // —— 合同收款信息（收款计划插在交货期条款之后、质保之前）——
  {
    key: 'payment',
    title: '合同收款信息',
    fields: [
      {
        key: 'payment_forms', label: '付款形式', source: 'reg', widget: 'checkbox', required: true,
        options: [
          { value: '银承', label: '银承' },
          { value: '商承', label: '商承' },
          { value: '电汇', label: '电汇' },
          { value: '现金', label: '现金' },
        ],
      },
      { key: 'payment_desc', label: '付款方式文字描述', source: 'reg', widget: 'text', required: true },
      { key: 'delivery_date', label: '合同交货期', source: 'native', widget: 'date', required: true },
      { key: 'delivery_clause', label: '交货期条款', source: 'reg', widget: 'text' },
    ],
    afterSlot: 'payment_terms',
    fieldsAfterSlot: [
      { key: 'warranty_period', label: '质保期限', source: 'reg', widget: 'text' },
      { key: 'warranty_amount', label: '质保金额', source: 'reg', widget: 'money' },
      { key: 'end_date', label: '到期日期', source: 'native', widget: 'date' },
    ],
  },
  {
    key: 'other',
    title: '合同其他信息',
    fields: [
      {
        key: 'industry', label: '行业分类', source: 'reg', widget: 'select', required: true,
        options: [
          { value: '工业升级', label: '工业升级' },
          { value: '循环经济', label: '循环经济' },
          { value: '基建民生', label: '基建民生' },
          { value: '技术运营', label: '技术运营' },
          { value: '其他', label: '其他' },
        ],
      },
      {
        key: 'region', label: '地区', source: 'reg', widget: 'select', required: true,
        options: [
          { value: '东北', label: '东北' },
          { value: '华北', label: '华北' },
          { value: '华东', label: '华东' },
          { value: '华南', label: '华南' },
          { value: '华中', label: '华中' },
          { value: '西南', label: '西南' },
          { value: '西北', label: '西北' },
          { value: '出口', label: '出口' },
        ],
      },
      { key: 'application_field', label: '应用领域', source: 'reg', widget: 'select', lookupFormCode: 'application_field', required: true },
      { key: 'application_material', label: '应用物料', source: 'reg', widget: 'select', lookupFormCode: 'application_material', required: true },
      { key: 'has_intelligence', label: '是否含智能化', source: 'reg', widget: 'radio', options: YES_NO, required: true },
      {
        key: 'smart_points', label: '智能点', source: 'reg', widget: 'checkbox',
        options: [
          { value: '远程监控', label: '远程监控' },
          { value: '智能润滑', label: '智能润滑' },
          { value: '移动称量', label: '移动称量' },
          { value: '视频监控', label: '视频监控' },
          { value: '抑尘系统', label: '抑尘系统' },
          { value: '产线自动化', label: '产线自动化' },
          { value: '其他', label: '其他' },
        ],
        showWhen: { field: 'has_intelligence', source: 'reg', equals: ['是'] },
        requiredWhen: { field: 'has_intelligence', source: 'reg', equals: ['是'] },
      },
      { key: 'remark', label: '备注', source: 'reg', widget: 'textarea' },
      { key: 'special_note', label: '特别提醒', source: 'reg', widget: 'text' },
    ],
    afterSlot: 'contract_files',
    fieldsAfterSlot: [
      { key: 'note_date', label: '日期时间', source: 'reg', widget: 'date' },
    ],
  },
  {
    key: 'logistics',
    title: '运费 / 地址 / 发货',
    fields: [
      {
        key: 'freight_payer', label: '运费承担方', source: 'reg', widget: 'radio', required: true,
        options: [
          { value: '我方', label: '我方' },
          { value: '需方', label: '需方' },
        ],
      },
      { key: 'contract_address', label: '合同约定地址', source: 'reg', widget: 'text' },
      { key: 'ship_address', label: '发货地址', source: 'reg', widget: 'text' },
      { key: 'ship_status', label: '发货状态', source: 'reg', widget: 'text' },
    ],
  },
  {
    key: 'accept',
    title: '验收',
    fields: [
      {
        // 简道云：财务审核节点填写（创建/编辑填报页不展示）
        key: 'accept_method', label: '验收方式', source: 'reg', widget: 'radio',
        availableOnCreate: false,
        options: [
          { value: '货到签收', label: '货到签收' },
          { value: '指导安装不含验收', label: '指导安装不含验收' },
          { value: '货到验收', label: '货到验收' },
          { value: '指导安装含验收', label: '指导安装含验收' },
          { value: '安装调试', label: '安装调试' },
        ],
      },
      {
        key: 'accept_materials', label: '验收所需资料', source: 'reg', widget: 'text',
        availableOnCreate: false,
      },
      {
        key: 'accept_date', label: '验收日期', source: 'reg', widget: 'date',
        availableOnCreate: false,
      },
    ],
    afterSlot: 'accept_files',
  },
]

/** 合同明细：产品类型 / 电控 / 外币 */
export const LINE_PRODUCT_TYPE_OPTS: RegOption[] = [
  { value: '复频筛', label: '复频筛' },
  { value: '高幅筛', label: '高幅筛' },
  { value: '其他筛分设备', label: '其他筛分设备' },
  { value: '输送设备', label: '输送设备' },
  { value: '破碎设备', label: '破碎设备' },
  { value: '除尘设备', label: '除尘设备' },
  { value: '污水净化设备', label: '污水净化设备' },
  { value: '智能装备', label: '智能装备' },
  { value: '其他', label: '其他' },
]

export const LINE_ELEC_CTRL_OPTS: RegOption[] = [
  { value: '含电控电缆', label: '含电控电缆' },
  { value: '含电控不含电缆', label: '含电控不含电缆' },
  { value: '不含电控不含电缆', label: '不含电控不含电缆' },
  { value: '不含电控含电缆', label: '不含电控含电缆' },
]

export const LINE_YES_NO_OPTS = YES_NO

/** 收款计划：付款方式 */
export const PAY_KIND_OPTS: RegOption[] = [
  { value: '预付', label: '预付' },
  { value: '发货', label: '发货' },
  { value: '到货', label: '到货' },
  { value: '验收', label: '验收' },
  { value: '调试', label: '调试' },
  { value: '质保', label: '质保' },
  { value: '其他', label: '其他' },
]

export function formatChangeType(v?: string | null): string {
  if (v === 'change' || v === '变动') return '变动'
  if (v === 'new' || v === '新增') return '新增'
  return v || '-'
}

/** 详情只读：选项值 → 标签；多选数组 join */
export function formatRegFieldValue(field: RegFieldDef, raw: unknown): string {
  if (raw == null || raw === '') return '-'
  const opts = field.options || []
  const labelOf = (v: unknown) => {
    const s = String(v)
    return opts.find((o) => o.value === s)?.label ?? s
  }
  if (Array.isArray(raw)) return raw.map(labelOf).filter(Boolean).join('、') || '-'
  return labelOf(raw)
}
