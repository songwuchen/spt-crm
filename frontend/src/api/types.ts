export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  traceId?: string
}

export interface PageData<T = unknown> {
  items: T[]
  total: number
  pageNo: number
  pageSize: number
}

export interface LoginRequest {
  username: string
  password: string
  totp_code?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserInfo {
  id: string
  tenant_id: string
  username: string
  real_name: string
  phone?: string
  email?: string
  avatar?: string
  roles: string[]
  permissions: string[]
}

export interface Customer {
  id: string
  customer_code?: string
  name: string
  short_name?: string
  industry?: string
  scale_level?: string
  region?: string
  province?: string
  city?: string
  district?: string
  region_code?: string
  address?: string
  website?: string
  owner_id?: string
  owner_name?: string
  source?: string
  level?: string
  status: string
  tags_json?: string[]
  custom_fields_json?: Record<string, unknown>
  remark?: string
  // 商机要素 / 采购意向（BANT 快照）
  intent_level?: string
  key_contact_id?: string
  demand?: string
  need_match_level?: string
  budget_amount?: number
  expected_purchase_date?: string
  headcount?: number
  // 公司档案增补
  industry_l1?: string
  industry_l2?: string
  industry_l3?: string
  country?: string
  postal_code?: string
  currency?: string
  // 归属 / 审计
  department_id?: string
  department_name?: string
  created_by_id?: string
  created_by_name?: string
  updated_by_id?: string
  updated_by_name?: string
  // 跟进 / 公海生命周期（含派生指标）
  last_activity_at?: string
  last_activity_by_id?: string
  last_activity_by_name?: string
  idle_days?: number | null
  expected_recycle_at?: string | null
  won_deal_count?: number
  pool_id?: string | null
  pool_source?: string
  pool_entered_at?: string
  created_at: string
  updated_at: string
}

export interface CustomerPool {
  id: string
  name: string
  description?: string
  region_scope?: string
  rules_json?: { enabled?: boolean; idle_days?: Record<string, number>; default_idle_days?: number } | null
  is_default: boolean
  is_active: boolean
  sort_order: number
  customer_count?: number
  created_at?: string
}

export interface Contact {
  id: string
  customer_id: string
  name: string
  title?: string
  role_type?: string
  phone?: string
  mobile?: string
  email?: string
  is_primary: boolean
  reports_to_id?: string
  remark?: string
}

export type LeadCategory = 'self_reported' | 'distributed'
export type LeadCountryType = 'domestic' | 'overseas'

export interface LeadProduct {
  id?: string
  product_name?: string
  product_spec?: string
  quantity?: number
  remark?: string
}

export interface Lead {
  id: string
  lead_code?: string
  title: string
  company_name?: string
  contact_name?: string
  contact_phone?: string
  contact_email?: string
  contact_raw_json?: Record<string, unknown>
  source?: string
  source_detail_json?: Record<string, unknown>
  demand_summary?: string
  industry?: string
  customer_type?: string
  category?: LeadCategory
  country_type?: LeadCountryType
  country_name?: string
  region?: string
  province?: string
  city?: string
  district?: string
  region_code?: string
  department_id?: string
  department_name?: string
  budget_range?: string
  owner_id?: string
  owner_name?: string
  created_by_id?: string
  created_by_name?: string
  biz_date?: string
  status: string
  review_status?: string
  review_flow_id?: string
  reject_reason?: string
  score: number
  converted_customer_id?: string
  remark?: string
  custom_fields_json?: Record<string, unknown>
  products?: LeadProduct[]
  created_at: string
  updated_at: string
}

export interface Department {
  id: string
  name: string
  parent_id?: string
  path: string
  sort_order: number
  leader_id?: string
  children: Department[]
}

export interface Role {
  id: string
  code: string
  name: string
  description?: string
  is_system: boolean
  data_scope?: string  // self / dept / all
  permissions: string[]
}

export interface PermissionItem {
  id: string
  code: string
  name: string
  group_name: string
}

export interface AuditLog {
  id: string
  user_id: string
  user_name?: string
  action: string
  resource_type: string
  resource_id?: string
  summary?: string
  detail?: Record<string, unknown>
  ip?: string
  user_agent?: string
  trace_id?: string
  created_at: string
}

// ==================== Phase 2: Project / Quote / Contract ====================

export interface OpportunityProject {
  id: string
  project_code: string
  customer_id?: string
  customer_name?: string
  name: string
  stage_code: string
  amount_expect?: number
  probability?: number
  close_date_expect?: string
  biz_date?: string
  competitors_json?: Record<string, unknown>
  key_requirements_json?: Record<string, unknown> | unknown[]
  risk_level?: string
  owner_id?: string
  owner_name?: string
  created_by_id?: string
  created_by_name?: string
  status: string
  custom_fields_json?: Record<string, unknown>
  remark?: string
  delivery_total?: number | null
  delivery_done?: number | null
  created_at: string
  updated_at: string
}

export interface ProjectStageHistory {
  id: string
  project_id: string
  from_stage: string
  to_stage: string
  changed_by_id?: string
  changed_by_name?: string
  note?: string
  created_at: string
}

export interface QuoteItem {
  id: string
  project_id: string
  quote_no: string
  current_version_no: number
  status: string
  created_by_id?: string
  created_by_name?: string
  assignee_id?: string
  assignee_name?: string
  department_id?: string
  department_name?: string
  created_at: string
  updated_at: string
  // Joined from get detail
  versions?: QuoteVersion[]
  current_version?: QuoteVersion
  lines?: QuoteLine[]
  // Joined from the tenant-wide list endpoint (current version summary)
  price_total?: number | null
  margin_rate?: number | null
  version_status?: string | null
}

export interface QuoteVersion {
  id: string
  quote_id: string
  version_no: number
  title?: string
  price_total?: number
  tax_rate?: number
  tax_total?: number
  discount_total?: number
  margin_rate?: number
  delivery_promise_date?: string
  validity_days?: number
  terms_summary_json?: Record<string, unknown>
  status: string
  created_at: string
}

export interface QuoteLine {
  id: string
  quote_version_id: string
  line_no: number
  item_type?: string
  item_name?: string
  item_code?: string
  spec?: string
  qty?: number
  unit?: string
  unit_price?: number
  line_total?: number
  cost_est?: number
  leadtime_days?: number
}

export interface ContractItem {
  id: string
  project_id: string
  contract_no: string
  current_version_no: number
  status: string
  signed_date?: string
  end_date?: string
  amount_total?: number | string
  payment_terms_json?: Record<string, unknown> | unknown[]
  delivery_terms_json?: Record<string, unknown> | unknown[]
  created_by_id?: string
  created_by_name?: string
  assignee_id?: string
  assignee_name?: string
  department_id?: string
  department_name?: string
  created_at: string
  updated_at: string
  versions?: ContractVersion[]
}

export interface ContractVersion {
  id: string
  contract_id: string
  version_no: number
  title?: string
  doc_attachment_id?: string
  key_clauses_json?: Record<string, unknown> | unknown[]
  risk_level?: string
  status: string
  created_at: string
}

export interface CostSnapshotItem {
  id: string
  quote_version_id: string
  snapshot_type: string
  price_total?: number
  cost_total?: number
  margin_rate?: number
  breakdown_json?: Record<string, number>
  line_snapshot_json?: Record<string, unknown>[]
  note?: string
  created_by_name?: string
  created_at: string
}

export interface QuoteSendLogItem {
  id: string
  quote_id: string
  quote_version_id: string
  channel: string
  to_list_json?: { name: string; contact: string }[]
  subject?: string
  body?: string
  attachments_json?: { filename: string; attachment_id?: string }[]
  status: string
  sent_by_id?: string
  sent_by_name?: string
  created_at: string
}

export interface ProjectHealthScore {
  project_id: string
  score: number
  max_score: number
  level: 'healthy' | 'attention' | 'warning' | 'critical'
  dimensions: Record<string, { score: number; max: number; label: string; detail: string }>
  risks: string[]
  stall_days: number
}

// ==================== Phase 3: Solution ====================

export interface SolutionItem {
  id: string
  project_id: string
  solution_no: string
  current_version_no: number
  status: string
  created_by_id?: string
  created_by_name?: string
  assignee_id?: string
  assignee_name?: string
  department_id?: string
  department_name?: string
  created_at: string
  updated_at: string
  // Joined from get detail
  versions?: SolutionVersion[]
  current_version?: SolutionVersion
}

export interface SolutionVersion {
  id: string
  solution_id: string
  version_no: number
  title?: string
  summary?: string
  config_json?: Record<string, unknown> | unknown[]
  risk_list_json?: Record<string, unknown> | unknown[]
  ai_insights_json?: Record<string, unknown>
  doc_attachment_id?: string
  status: string
  created_at: string
}

// ==================== Phase 4: Delivery ====================

export interface ErpOrderLink {
  id: string
  project_id: string
  erp_system_code?: string
  erp_order_no?: string
  sync_status: string
  remark?: string
  created_at: string
}

export interface DeliveryMilestone {
  id: string
  project_id: string
  milestone_code: string
  name?: string
  plan_date?: string
  actual_date?: string
  status: string
  source_type: string
  sort_order: number
  note?: string
  assignee_id?: string
  assignee_name?: string
  department_id?: string
  department_name?: string
  attachment_count?: number
  created_at: string
}

// ==================== Phase 5: Payment ====================

export interface InvoiceItem {
  id: string
  project_id: string
  invoice_no: string
  amount?: number
  invoice_date?: string
  status: string
  erp_ref_json?: Record<string, unknown>
  remark?: string
  created_by_id?: string
  created_by_name?: string
  created_at: string
}

export interface PaymentPlanItem {
  id: string
  project_id: string
  plan_no: string
  due_date?: string
  amount?: number
  trigger_milestone_code?: string
  source_contract_id?: string
  status: string
  remark?: string
  assignee_id?: string
  assignee_name?: string
  department_id?: string
  department_name?: string
  created_at: string
}

export interface PaymentRecordItem {
  id: string
  project_id: string
  received_date?: string
  amount?: number
  channel?: string
  reference_no?: string
  matched_plan_id?: string
  remark?: string
  created_by_id?: string
  created_by_name?: string
  created_at: string
}

// ==================== Phase 6: Change Request ====================

export interface ChangeRequestItem {
  id: string
  project_id: string
  change_no: string
  change_type: string
  from_version_ref_json?: Record<string, unknown>
  to_version_ref_json?: Record<string, unknown>
  reason?: string
  impact_json?: Record<string, unknown>
  status: string
  created_by_id?: string
  created_by_name?: string
  assignee_id?: string
  assignee_name?: string
  department_id?: string
  department_name?: string
  created_at: string
  updated_at: string
}

// ==================== Phase 7: Service ====================

export interface ServiceTicketItem {
  id: string
  customer_id?: string
  project_id?: string
  order_id?: string
  ticket_no: string
  type: string
  priority: string
  status: string
  description?: string
  resolution?: string
  ai_summary_json?: Record<string, unknown>
  assigned_to_id?: string
  assigned_to_name?: string
  created_by_id?: string
  created_by_name?: string
  sla_respond_by?: string
  sla_resolve_by?: string
  sla_responded_at?: string
  sla_resolved_at?: string
  satisfaction_score?: number
  satisfaction_comment?: string
  satisfaction_at?: string
  created_at: string
  updated_at: string
}

export interface RenewalItem {
  id: string
  customer_id: string
  name: string
  amount_expect?: number
  close_date_expect?: string
  probability?: number
  related_asset_json?: Record<string, unknown>
  status: string
  owner_id?: string
  owner_name?: string
  remark?: string
  created_at: string
  updated_at: string
}

// ==================== Phase 9: Activity ====================

export interface ActivityItem {
  id: string
  biz_type: string
  biz_id: string
  activity_type: string
  subject?: string
  content?: string
  contact_id?: string
  contact_name?: string
  result_json?: Record<string, unknown>
  next_follow_date?: string | null
  biz_name?: string | null
  mentions_json?: { user_id: string; user_name: string }[]
  pinned?: boolean
  created_by_id?: string
  created_by_name?: string
  created_at: string
  updated_at: string
}

// ==================== Phase 10: AI Center ====================

export interface AiTaskItem {
  id: string
  task_type: string
  biz_type?: string
  biz_id?: string
  status: string
  priority: number
  model_name?: string
  prompt_template_id?: string
  input_ref_json?: Record<string, unknown>
  budget_json?: Record<string, unknown>
  token_in?: number
  token_out?: number
  cost_est?: number
  retry_count: number
  error_message?: string
  created_by_id?: string
  created_by_name?: string
  created_at: string
  updated_at: string
  result?: AiResultItem
}

export interface AiResultItem {
  id: string
  ai_task_id: string
  result_json?: Record<string, unknown>
  evidence_json?: Record<string, unknown>
  risk_level?: string
  quality_score?: number
  created_at: string
}

export interface AiPromptTemplateItem {
  id: string
  code: string
  name: string
  task_type: string
  template_text?: string
  output_schema_json?: Record<string, unknown>
  guardrails_json?: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

// ==================== Approval ====================

export interface ApprovalFlowItem {
  id: string
  biz_type: string
  biz_id: string
  title?: string
  status: string
  approval_mode?: string
  current_node: number
  total_nodes: number
  submitted_by_id?: string
  submitted_by_name?: string
  parent_flow_id?: string
  revision_no?: number
  created_at: string
  updated_at: string
  tasks?: ApprovalTaskItem[]
  biz_detail?: Record<string, string>
}

export interface ApprovalTaskItem {
  id: string
  flow_id: string
  node_order: number
  assignee_id: string
  assignee_name?: string
  status: string
  comment?: string
  decided_at?: string
  created_at: string
}

export interface ApprovalPendingItem extends ApprovalTaskItem {
  flow: ApprovalFlowItem
}

// ==================== ACL Share ====================

export interface AclShareItem {
  id: string
  biz_type: string
  biz_id: string
  shared_to_type: string
  shared_to_id: string
  shared_to_name?: string
  permission: string
  shared_by_name?: string
  created_at: string
}

export interface ProjectMember {
  id: string
  project_id: string
  user_id: string
  user_name?: string
  member_role?: string
  department_id?: string
  department_name?: string
  permission: string
  added_by_id?: string
  added_by_name?: string
  created_at: string
}

export interface Order {
  id: string
  order_no: string
  customer_id: string
  project_id?: string
  contract_id?: string
  title?: string
  amount?: number
  currency?: string
  status: string
  order_date?: string
  delivery_date?: string
  owner_id?: string
  owner_name?: string
  remark?: string
  lines?: OrderLine[]
  ship_status?: 'none' | 'partial' | 'full'
  created_at: string
  updated_at?: string
}

export interface OrderLine {
  id?: string
  product_id?: string
  product_name: string
  spec?: string
  unit?: string
  quantity: number
  unit_price: number
  amount?: number
  shipped_quantity?: number
  sort_order?: number
}

export interface Tender {
  id: string
  tender_no: string
  customer_id: string
  project_id?: string
  title: string
  bid_amount?: number
  budget_amount?: number
  status: string
  submit_date?: string
  open_date?: string
  result?: string
  owner_id?: string
  owner_name?: string
  remark?: string
  created_at: string
  updated_at?: string
}

export interface Commission {
  id: string
  record_no: string
  project_id?: string
  contract_id?: string
  customer_id?: string
  customer_name?: string
  owner_id?: string
  owner_name?: string
  department_id?: string
  department_name?: string
  signed_date?: string
  contract_amount: number
  received_amount: number
  deduction_freight: number
  deduction_service: number
  deduction_entertain: number
  deduction_rebate: number
  commission_mode?: string  // rate=按比例 / amount=按固定金额
  commission_rate: number
  commission_amount?: number  // 固定提成金额（amount 模式）
  settle_rate: number
  accrued_amount: number
  paid_amount: number
  current_amount: number
  status: string
  remark?: string
  created_by_name?: string
  created_at: string
}

export interface CommissionPayout {
  id: string
  commission_id: string
  paid_at?: string
  amount: number
  method?: string
  remark?: string
  created_by_name?: string
  created_at: string
}

export interface CommissionRule {
  id: string
  name: string
  scope_type: string
  department_id?: string
  department_name?: string
  rate: number
  min_amount?: number
  enabled: boolean
  sort_order: number
  remark?: string
}

export interface CommissionSummary {
  owner_id?: string
  owner_name: string
  count: number
  contract_total: number
  received_total: number
  accrued_total: number
  paid_total: number
  payable_total: number
}

export interface ArAgingRow {
  customer_id?: string
  customer_name: string
  owner_id?: string
  owner_name?: string
  contract_total: number
  received_total: number
  outstanding: number
  d0_30: number
  d31_60: number
  d61_90: number
  d91_180: number
  d180p: number
}

export interface ArAgingReport {
  summary: Record<string, number>
  buckets: string[]
  rows: ArAgingRow[]
  total?: number // 传分页参数时返回：客户总数（用于后端分页）
}

export interface DebtTransfer {
  id: string
  transfer_no: string
  customer_id?: string
  customer_name?: string
  transfer_type: string
  from_department_name?: string
  from_owner_name?: string
  to_department_id?: string
  to_department_name?: string
  debt_amount?: number
  contact?: string
  contact_phone?: string
  debt_note?: string
  reason?: string
  deadline?: string
  assess_date?: string
  commitment?: string
  status: string
  claimed_by_name?: string
  claimed_department_name?: string
  claimed_at?: string
  created_by_name?: string
  created_at: string
}

export interface CollectionFollowUp {
  id: string
  customer_id?: string
  customer_name?: string
  transfer_id?: string
  follow_date?: string
  method?: string
  feedback?: string
  expected_date?: string
  amount_promised?: number
  next_action?: string
  created_by_name?: string
  created_at: string
}

export interface Guarantee {
  id: string
  guarantee_no: string
  type: string
  direction: string
  contract_id?: string
  project_id?: string
  customer_id?: string
  customer_name?: string
  amount?: number
  issuer?: string
  fee?: number
  rate?: number
  effective_date?: string
  expiry_date?: string
  return_date?: string
  status: string
  owner_id?: string
  owner_name?: string
  remark?: string
  created_by_name?: string
  created_at: string
}

export interface GuaranteeSummary {
  by_status: Record<string, { count: number; amount: number }>
  active_amount: number
  expiring_30d: number
}

export interface CustomerEquipment {
  id: string
  customer_id: string
  customer_name?: string
  name: string
  category?: string
  spec?: string
  supplier?: string
  is_competitor: boolean
  usage_years?: number
  quantity?: number
  condition?: string
  replace_plan_date?: string
  spare_usage?: string
  remark?: string
  created_by_name?: string
  created_at: string
}

export interface CustomerProcessSurvey {
  id: string
  customer_id: string
  customer_name?: string
  industry?: string
  main_products?: string
  annual_output?: string
  branch_info?: string
  process_desc?: string
  pain_points?: string
  survey_date?: string
  owner_id?: string
  owner_name?: string
  remark?: string
  created_by_name?: string
  created_at: string
}

export interface ServiceMeasurement {
  id: string
  record_no: string
  ticket_id?: string
  customer_id?: string
  customer_name?: string
  service_date?: string
  engineer_id?: string
  engineer_name?: string
  industry?: string
  equipment_name?: string
  equipment_model?: string
  product_no?: string
  motor_power_kw?: number
  amplitude_mm?: number
  material_name?: string
  layer_thickness_mm?: number
  feed_size_mm?: number
  screen_efficiency?: number
  throughput_tph?: number
  source_temp_c?: number
  ambient_temp_c?: number
  running_current_a?: number
  daily_run_hours?: number
  service_rating?: string
  product_rating?: string
  result_desc?: string
  issues?: string
  remark?: string
  created_by_name?: string
  created_at: string
}

export interface MeasurementModelStat {
  equipment_model: string
  count: number
  avg_efficiency?: number
  avg_throughput?: number
  avg_current?: number
}

export interface CustomerReport {
  customer: { id: string; name: string; customer_code?: string }
  summary: Record<string, number>
  projects: Array<{ id: string; project_code: string; name: string; stage_code?: string; amount_expect?: number; status?: string; created_at?: string }>
  quotes: Array<{ id: string; quote_no: string; project_id?: string; current_version_no?: number; status?: string; amount?: number; created_at?: string }>
  contracts: Array<{ id: string; contract_no: string; project_id?: string; status?: string; signed_date?: string; amount_total?: number; created_at?: string }>
  orders: Array<{ id: string; order_no: string; title?: string; amount?: number; currency?: string; status?: string; order_date?: string; delivery_date?: string }>
  tenders: Array<{ id: string; tender_no: string; title?: string; bid_amount?: number; budget_amount?: number; status?: string; result?: string; submit_date?: string; open_date?: string }>
  payment_plans: Array<{ id: string; plan_no?: string; due_date?: string; amount?: number; status?: string }>
  payment_records: Array<{ id: string; received_date?: string; amount?: number; channel?: string; reference_no?: string }>
  tickets: Array<{ id: string; ticket_no: string; type?: string; status?: string; priority?: string; created_at?: string }>
  deliveries: Array<{ id: string; milestone_code: string; name?: string; plan_date?: string; actual_date?: string; status?: string }>
}

// Shared enum label maps
export const sourceLabels: Record<string, string> = {
  expo: '展会', referral: '转介绍', ad: '广告',
  inbound: '官网/入站', partner: '合作伙伴', call: '电话',
}

// 行业字典 (DataDictionary dict_type="industry"; see backend/scripts/seed_lead_dicts.py).
// Migrated customers may store either these codes or free-text Chinese — map known
// codes to labels and pass anything else through unchanged.
export const industryLabels: Record<string, string> = {
  screening_metallurgy: '筛分分选-冶金',
  screening_mining: '筛分分选-矿山',
  screening_aggregate: '筛分分选-砂石',
  screening_coking: '筛分分选-焦化',
  screening_coal: '筛分分选-煤炭',
  screening_power: '筛分分选-电力',
  screening_chemical: '筛分分选-化工',
  screening_pharma: '筛分分选-医药',
  screening_spare_parts: '筛分分选-备件',
  circular_economy: '循环经济',
  scrap_steel: '废钢利用',
  bulk_material_intelligent: '智能化大宗物料管理',
}

// Fallback options for useDataDict('industry') when the dict API is unavailable —
// mobile uses the live dict (same as desktop) and falls back to these business codes.
export const industryFallback = Object.entries(industryLabels).map(([value, label]) => ({ label, value }))

export const stageLabels: Record<string, string> = {
  S1: '线索确认', S2: '需求分析', S3: '方案报价',
  S4: '商务谈判', S5: '合同签订', S6: '交付验收',
}

export const stageColors: Record<string, string> = {
  S1: 'bg-slate-100 text-slate-600 border-slate-200',
  S2: 'bg-blue-100 text-blue-700 border-blue-200',
  S3: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  S4: 'bg-amber-100 text-amber-700 border-amber-200',
  S5: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  S6: 'bg-green-100 text-green-700 border-green-200',
}

export const riskLabels: Record<string, string> = { L: '低', M: '中', H: '高' }
export const riskColors: Record<string, string> = {
  L: 'bg-emerald-50 text-emerald-600 border-emerald-100',
  M: 'bg-amber-50 text-amber-600 border-amber-100',
  H: 'bg-red-50 text-red-600 border-red-100',
}
