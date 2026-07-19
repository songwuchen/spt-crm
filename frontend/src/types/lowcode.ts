// 扩展平台(低代码) — 前端类型。移植自 spt-lowcode types/form.ts,与后端 FieldDefinition/规则 schema 对齐。

export type FieldType =
  | 'text' | 'textarea' | 'number' | 'amount'
  | 'date' | 'datetime'
  | 'select' | 'multi_select' | 'radio' | 'checkbox' | 'switch'
  | 'person' | 'person_multi' | 'department' | 'department_multi'
  | 'file' | 'image' | 'detail_table'
  | 'formula' | 'auto_number'
  | 'related_doc' | 'address' | 'location' | 'cascade' | 'rich_text'
  | 'signature' | 'select_data' | 'relation' | 'sub_table_data'

export interface OptionItem {
  label: string
  value: string
  [k: string]: unknown
}

export interface FieldDefinition {
  id: string
  type: FieldType
  label: string
  placeholder?: string
  description?: string
  required?: boolean
  default_value?: unknown
  options?: OptionItem[]
  props?: Record<string, unknown>
  detail_table_columns?: FieldDefinition[]
  is_indexed?: boolean
  span?: number // 栅格: 6/8/12/24, 默认 24
  // 字段级权限(角色 code)。空/缺省 = 不限制。递进：隐藏 > 脱敏 > 只读。
  // visible_roles: 谁可见; unmask_roles: 谁可见明文(其余人得 "***"); edit_roles: 谁可编辑。
  visible_roles?: string[] | null
  unmask_roles?: string[] | null
  edit_roles?: string[] | null
  masked?: boolean // 后端读取时对已脱敏字段的标记
  readonly?: boolean // 后端 get_instance 对不可编辑字段的标记(只读渲染)
  // 原生字段(业务表内置列，如线索的 industry)标记。其值存业务列而非 custom_fields_json，
  // 设计器里不可删除/改类型；system_required 为真时连「必填」也不可改（列本身 NOT NULL）。
  native?: boolean
  system_required?: boolean
  options_source?: string | null
  /** 仅当租户确实改过标签时才有值；业务表单据此覆盖自己的默认 label。 */
  label_override?: string
  /** 派生显示键(owner_id → owner_name)，隐藏/脱敏时须连带处理。 */
  companions?: string[]
}

/** 业务实体表单的完整字段策略：原生字段 + 扩展字段 + 规则。 */
export interface EntityFormSchema {
  native_fields: FieldDefinition[]
  field_definitions: FieldDefinition[]
  rule_definitions: FormRule[]
}

export interface FormRule {
  id: string
  type: 'visibility' | 'validation' | 'formula' | 'readonly' | 'required'
  // 目标字段: 单个(target_field_id)或多个(target_field_ids)。规则引擎优先取 target_field_ids。
  target_field_id?: string
  target_field_ids?: string[]
  condition: RuleCondition
  action: Record<string, unknown>
}

export type RuleConditionNode = RuleConditionItem | RuleConditionGroup

export interface RuleConditionItem {
  field: string
  operator: string
  value?: unknown
}

export interface RuleConditionGroup {
  rel: 'and' | 'or'
  cond: RuleConditionNode[]
}

export interface RuleCondition {
  rel?: 'and' | 'or'
  cond?: RuleConditionNode[]
  field?: string
  operator?: string
  value?: unknown
}

export function isConditionGroup(node: RuleConditionNode): node is RuleConditionGroup {
  return !!node && Array.isArray((node as RuleConditionGroup).cond)
}

export type FieldPermissionAccess = 'editable' | 'readonly' | 'hidden' | 'required' | 'masked'

export interface FieldPermission {
  fieldId: string
  access: FieldPermissionAccess
}

export interface FieldState {
  visible: boolean
  readonly: boolean
  required: boolean
  /** 脱敏：字段仍显示但只给 "***"，且一律不可编辑（看不到明文就不该覆盖真实值）。 */
  masked: boolean
}

export interface FieldComponentProps {
  field: FieldDefinition
  value: unknown
  onChange: (value: unknown) => void
  disabled: boolean
  mode: 'edit' | 'readonly' | 'design'
  allValues?: Record<string, unknown>
  fieldStates?: Record<string, FieldState>
}

// ===== 模板 / 版本 / 实例 =====

export interface FormTemplate {
  id: string
  name: string
  code: string
  description?: string
  category?: string
  icon?: string
  status: string          // draft / published / deprecated
  current_version: number
  sort_order: number
  is_system?: boolean
  entity_type?: string
}

export interface BuiltinTemplate {
  key: string
  name: string
  category?: string
  icon?: string
  description?: string
  field_count: number
}

export interface FormVersion {
  id: string
  template_id: string
  version_number: number
  field_definitions: FieldDefinition[]
  layout_definition: Record<string, unknown>
  rule_definitions: FormRule[]
  status: string
  published_at?: string | null
}

export interface FormInstance {
  id: string
  template_id: string
  business_no?: string | null
  title?: string | null
  status: string
  initiator_id: string
  amount?: number | null
  form_data: Record<string, unknown>
  created_at: string
}

export interface FormInstanceDetail extends FormInstance {
  field_definitions: FieldDefinition[]
  rule_definitions: FormRule[]
}

// ===== 审批流程 =====

export type WfNodeType = 'start' | 'approval' | 'cc' | 'condition' | 'parallel' | 'merge' | 'end'
export type WfMultiMode = 'or_sign' | 'countersign' | 'sequential'

export type WfTimeoutAction = 'notify' | 'auto_approve' | 'auto_reject' | 'auto_transfer'
export interface WfTimeout {
  hours: number
  action: WfTimeoutAction
  transfer_to?: string | null   // auto_transfer 时的接收人
}
export type ApproverType =
  | 'specified_user' | 'specified_role' | 'specified_post'
  | 'direct_supervisor' | 'dept_head' | 'multi_level_superior'
  | 'dept_members' | 'creator' | 'form_field_person' | 'form_field_dept'
  | 'initiator_self_select' | 'mixed'

export interface WfApproverRule {
  type: ApproverType
  value?: unknown
  node_id?: string
  include_sub?: boolean
  levels?: number
}

export interface WfNode {
  id: string
  type: WfNodeType
  name: string
  approver_rule?: WfApproverRule
  multi_mode?: WfMultiMode
  empty_strategy?: 'auto_approve' | 'terminate'
  timeout?: WfTimeout | null            // 审批节点超时(SLA)配置
  position?: { x: number; y: number }  // 可视化画布节点坐标
}

export interface WfRoute {
  id: string
  source: string
  target: string
  condition?: { rel: 'and' | 'or'; cond: { field: string; operator: string; value?: unknown }[] } | null
}

export interface WfDefinition {
  id: string
  name: string
  code: string
  description?: string
  category?: string
  status: string
  current_version: number
  form_template_id?: string | null
  biz_type?: string | null
}

export interface WfDesign {
  node_definitions: WfNode[]
  route_definitions: WfRoute[]
  approver_rules: WfApproverRule[]
}

export interface WfTodoItem {
  task_id: string
  status: string
  process_instance_id: string
  title?: string | null
  business_no?: string | null
  initiator_id?: string
  initiator_name?: string | null
  process_status?: string
  // 承载的业务单据（线索/合同/订单…），用于把待办关联回业务详情页
  biz_type?: string | null
  biz_id?: string | null
  created_at?: string
  action_at?: string
  on_behalf_of?: boolean       // 代理审批：该待办由本人代委托人处理
  delegator_id?: string | null
  delegator_name?: string | null
}

export interface WfTimelineItem {
  action: string
  actor_id: string
  actor_name?: string
  opinion?: string
  at?: string
}

export interface WfInstanceDetail {
  id: string
  title?: string | null
  business_no?: string | null
  status: string
  initiator_id: string
  form_instance_id?: string | null
  biz_type?: string | null
  started_at?: string | null
  completed_at?: string | null
  timeline: WfTimelineItem[]
  tasks: { id: string; assignee_id: string; status: string; opinion?: string; task_order: number }[]
  comments: { user_id: string; user_name?: string; content: string; at?: string }[]
  approval_nodes?: { id: string; name: string }[]  // 可退回的审批节点(退回选择)
}

// ===== 仪表盘 =====

export type ChartType =
  | 'bar' | 'line' | 'area' | 'pie' | 'funnel' | 'radar'
  | 'scatter' | 'gauge' | 'dual_axis' | 'pivot' | 'number'

export interface AggDimensionDef { field_id: string; granularity?: 'year' | 'month' | 'day' }
export interface AggMetricDef { op: 'count' | 'count_distinct' | 'sum' | 'avg' | 'max' | 'min'; field_id?: string }
export interface AggFilterDef { field_id: string; operator: string; value?: unknown }

export interface DashDataSource {
  source?: 'form' | 'crm'   // 默认 form(自定义表单); crm=CRM 业务数据
  template_id?: string      // form 数据源
  entity?: string           // crm 数据源(customer/lead/order)
  dimensions: AggDimensionDef[]
  metrics: AggMetricDef[]
  filters?: AggFilterDef[]
}

export interface CrmSource {
  entity: string
  label: string
  dimensions: { field: string; label: string; date?: boolean }[]
  metrics: { op: string; field?: string; label: string }[]
}

export interface DashComponent {
  id: string
  type: ChartType
  title: string
  layout: { x: number; y: number; w: number; h: number }
  data_source: DashDataSource
}

export interface Dashboard {
  id: string
  name: string
  description?: string
  components: DashComponent[]
  styles: Record<string, unknown>
}

export interface AggregateResult {
  rows: Record<string, unknown>[]
  dimensions: string[]
  metrics: string[]
}
