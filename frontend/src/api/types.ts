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
  address?: string
  website?: string
  owner_id?: string
  owner_name?: string
  source?: string
  level?: string
  status: string
  tags_json?: string[]
  remark?: string
  created_at: string
  updated_at: string
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
  region?: string
  budget_range?: string
  owner_id?: string
  owner_name?: string
  status: string
  score: number
  converted_customer_id?: string
  remark?: string
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
  name: string
  stage_code: string
  amount_expect?: number
  probability?: number
  close_date_expect?: string
  competitors_json?: Record<string, unknown>
  key_requirements_json?: Record<string, unknown>
  risk_level?: string
  owner_id?: string
  owner_name?: string
  status: string
  remark?: string
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
  created_at: string
  updated_at: string
  // Joined from get detail
  versions?: QuoteVersion[]
  current_version?: QuoteVersion
  lines?: QuoteLine[]
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
  amount_total?: number
  payment_terms_json?: Record<string, unknown>
  delivery_terms_json?: Record<string, unknown>
  created_by_id?: string
  created_by_name?: string
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
  key_clauses_json?: Record<string, unknown>
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
  config_json?: Record<string, unknown>
  risk_list_json?: Record<string, unknown>
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
  status: string
  remark?: string
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
  created_at: string
  updated_at: string
}

// ==================== Phase 7: Service ====================

export interface ServiceTicketItem {
  id: string
  customer_id?: string
  project_id?: string
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

// Shared enum label maps
export const sourceLabels: Record<string, string> = {
  expo: '展会', referral: '转介绍', ad: '广告',
  inbound: '官网/入站', partner: '合作伙伴', call: '电话',
}

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
