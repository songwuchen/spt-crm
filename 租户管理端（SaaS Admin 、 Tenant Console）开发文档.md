下面给你一份**“租户管理端（SaaS Admin / Tenant Console）开发文档”**，目标是：让你们的离散制造 CRM + AI 平台具备**多租户、计费/配额、权限/组织、AI预算治理、集成配置、审计与合规**等“可商用”能力。内容按：**范围→架构→数据模型→接口→页面→权限→审计→任务拆解**写，基本可以直接拆 Jira 开发。

---

# 1. 范围与角色

## 1.1 租户管理端包含两类后台

1. **平台级管理端（Platform Admin / 超级管理员）**

* 管所有租户：开通/停用/配额/计费计划/全局模型与策略/全局审计

2. **租户级管理端（Tenant Admin / 租户管理员）**

* 管本租户：组织架构、用户与角色、权限策略、阶段/Gate、审批策略、AI策略与预算、集成配置、审计报表

> 如果你们早期不想做两个前端，也可以同一套前端用 `admin_scope = platform|tenant` 控制菜单与接口。

---

# 2. 总体架构与边界

## 2.1 独立的“管理域”服务（建议）

* tenant-service：租户、计划、配额、开通、停用
* iam-service：用户、部门、角色、权限点、SSO
* policy-service：阶段/Gate/红线/审批/字段脱敏/密级策略
* ai-governance-service：模型路由、预算、限流、日志、成本归集
* integration-service：ERP/MES/钉钉/企微/Webhook/Outbox
* audit-service：审计日志、导出、合规留存

> 你们可以物理上一个服务实现，逻辑上按域拆即可。

---

# 3. 数据模型（管理端相关表）

## 3.1 平台级（Platform）

### platform_tenant

* id (PK)
* tenant_code（唯一，外部识别）
* name
* status (active|suspended|deleted)
* plan_id（套餐）
* region_code（数据区域，若做多区）
* created_at, updated_at

### tenant_plan（套餐）

* id
* name
* pricing_json（价格信息，可先不启用）
* limits_json（默认配额）
* features_json（功能开关：AI、审批、RAG、合同解析等）
* status

**limits_json 示例**

```json
{
  "user_seats": 100,
  "storage_gb": 500,
  "ai_monthly_tokens": 20000000,
  "ai_monthly_cost": 300,
  "vector_docs": 200000,
  "api_rate_limit_rpm": 600
}
```

### tenant_usage_meter（计量）

* id, tenant_id
* metric_code（user_active / ai_tokens / ai_cost / storage_bytes / api_calls）
* period（月/日）
* value
* updated_at

### platform_model_catalog（平台模型目录）

* id
* provider (doubao|openai|local)
* model_name
* capability_json（text/vision/asr/embedding）
* price_policy_json（单价/折扣）
* status

---

## 3.2 租户级（Tenant）

### tenant_profile（租户配置）

* tenant_id (PK)
* timezone, locale
* logo_attachment_id
* security_policy_json（密码/2FA/登录限制）
* data_retention_days（审计/聊天/附件保留）
* created_at, updated_at

### tenant_feature_toggle

* id, tenant_id
* feature_code（ai_center, rag, contract_risk, quote_risk...）
* enabled (bool)
* config_json（细粒度参数）

### tenant_quota_override（租户配额覆盖）

* id, tenant_id
* limits_json（覆盖 plan 默认值）
* effective_from, effective_to

---

## 3.3 组织与权限（IAM）

### user

* id, tenant_id
* username/email/mobile
* display_name
* status (active|locked|disabled)
* last_login_at
* created_at

### department

* id, tenant_id
* parent_id
* name
* path（如 `/总部/销售部/华北组`）
* sort_no

### user_department

* tenant_id, user_id, department_id（联合主键）
* is_primary（主部门）

### role

* id, tenant_id
* role_code（sales, sales_mgr, tech, finance, legal, service, admin）
* name
* scope_type（tenant/global/custom）
* created_at

### permission

* id
* perm_code（如 `quote.view_cost`, `attachment.download_restricted`）
* name
* module_code

### role_permission

* tenant_id, role_id, perm_id（联合主键）

### acl_share（对象级共享授权，业务端用）

* tenant_id, biz_type, biz_id, to_type, to_id, rights_json, expires_at

---

## 3.4 策略配置（Policy）

### stage_definition（阶段与Gate）

* id, tenant_id
* stage_code, name
* allowed_transitions_json
* gate_rules_json
* enabled

### margin_policy（毛利红线）

* id, tenant_id
* policy_code
* scope_json（产品线/客户等级/区域）
* redline_rate
* action (block|need_approval|warn)
* enabled

### approval_policy（审批策略）

* id, tenant_id
* policy_code
* biz_type（quote_version/contract_version/change_request）
* condition_json（金额/毛利/客户等级/密级）
* flow_template_json（节点/负责人规则）
* enabled

### field_mask_policy（字段脱敏）

* id, tenant_id
* entity_code（quote_version, cost_snapshot...）
* fields_json
* allow_roles_json
* allow_conditions_json
* mask_mode (null|range|hash)

### secrecy_policy（密级策略）

* id, tenant_id
* doc_type
* default_level
* download_rule_json

---

## 3.5 AI 治理（AI Governance）

### tenant_ai_policy

* id, tenant_id
* task_type（quote_risk/contract_risk/demand_extract…）
* model_route_json（优先模型、降级模型）
* budget_json（max_tokens/max_cost/月预算占比）
* trigger_json（在哪些Gate强制/哪些状态触发）
* guardrails_json（脱敏/禁止项）
* enabled

### tenant_ai_budget（月度预算）

* tenant_id, period (YYYY-MM)
* budget_cost, used_cost
* budget_tokens, used_tokens
* hard_limit (bool)

### tenant_rate_limit（限流）

* id, tenant_id
* key_code（api_rpm, ai_rpm, upload_rpm）
* limit_value
* window_seconds

---

## 3.6 集成与密钥（Integration）

### integration_endpoint

* id, tenant_id
* system_code（erp_k3, mes_xxx, dingtalk, wecom）
* base_url
* auth_type（apikey/oauth2/basic）
* secret_ref_id（指向密钥表）
* status

### secret_store（密钥托管）

* id, tenant_id
* name
* secret_type（api_key/oauth_client/tenant_token）
* cipher_text（加密存储）
* created_at, rotated_at

### webhook_subscription

* id, tenant_id
* event_types_json
* target_url
* secret_ref_id
* status

---

## 3.7 审计与合规（Audit）

### audit_log

* id, tenant_id
* actor_user_id
* action_code（user.create, role.grant, policy.update, attachment.download…）
* biz_type, biz_id
* diff_json
* ip, user_agent
* trace_id
* created_at

### export_job（导出任务）

* id, tenant_id
* job_type（audit_export/user_export/policy_export）
* params_json
* status
* result_attachment_id
* created_at

---

# 4. 租户管理端 API 设计（按域）

统一：

* Base：`/api/admin/v1/`
* 权限：platform_admin 与 tenant_admin 分 scope
* 幂等：`Idempotency-Key`

## 4.1 平台级：租户开通与停用

### 创建租户

`POST /api/admin/v1/platform/tenants`

```json
{
  "tenant_code": "T001",
  "name": "若邻智能-测试租户",
  "plan_id": 2,
  "admin_user": { "email": "admin@xxx.com", "display_name": "租户管理员" }
}
```

行为：

* 创建 tenant + profile
* 创建租户管理员用户 + admin 角色绑定
* 初始化默认策略（stage/margin/approval/ai_policy）

### 停用/启用租户

`POST /api/admin/v1/platform/tenants/{id}/status`

```json
{ "status": "suspended", "reason": "欠费" }
```

规则：

* suspended：业务端所有请求返回 `403 tenant_suspended`
* deleted：仅软删，保留审计（合规）

### 修改套餐/配额

`PUT /api/admin/v1/platform/tenants/{id}/plan`

```json
{ "plan_id": 3, "quota_override": { "user_seats": 300, "ai_monthly_cost": 800 } }
```

---

## 4.2 租户级：组织用户管理（IAM）

### 用户列表/创建/禁用

* `GET /api/admin/v1/tenant/users`
* `POST /api/admin/v1/tenant/users`
* `POST /api/admin/v1/tenant/users/{id}/status`

### 部门树

* `GET /api/admin/v1/tenant/departments/tree`
* `POST /api/admin/v1/tenant/departments`
* `PUT /api/admin/v1/tenant/departments/{id}`
* `DELETE /api/admin/v1/tenant/departments/{id}`（需校验无子部门/无用户）

### 角色与权限

* `GET /api/admin/v1/tenant/roles`
* `POST /api/admin/v1/tenant/roles`
* `PUT /api/admin/v1/tenant/roles/{id}`
* `POST /api/admin/v1/tenant/roles/{id}/grant_permissions`

```json
{ "perm_codes": ["quote.view_cost","attachment.download_restricted"] }
```

---

## 4.3 策略配置（Policy）

### 阶段与Gate

* `GET /api/admin/v1/tenant/policies/stages`
* `PUT /api/admin/v1/tenant/policies/stages/{stage_code}`
  （直接更新 gate_rules_json，必须 schema 校验）

### 毛利红线

* `GET /api/admin/v1/tenant/policies/margin`
* `POST /api/admin/v1/tenant/policies/margin`
* `PUT /api/admin/v1/tenant/policies/margin/{id}`

### 审批策略

* `GET /api/admin/v1/tenant/policies/approval`
* `POST /api/admin/v1/tenant/policies/approval`

### 字段脱敏/密级

* `GET /api/admin/v1/tenant/policies/field_mask`
* `GET /api/admin/v1/tenant/policies/secrecy`

---

## 4.4 AI 治理（预算/模型/触发）

### AI策略

* `GET /api/admin/v1/tenant/ai/policies`
* `PUT /api/admin/v1/tenant/ai/policies/{task_type}`

```json
{
  "enabled": true,
  "model_route": { "primary": "doubao-pro", "fallback": "doubao-lite" },
  "budget": { "max_tokens": 1800, "max_cost": 0.2 },
  "trigger": { "required_in_gates": ["S4_QUOTE","S6_WON"] },
  "guardrails": { "no_price_leak": true, "mask_fields": ["bottom_price"] }
}
```

### 月度预算

* `GET /api/admin/v1/tenant/ai/budget?period=2026-02`
* `PUT /api/admin/v1/tenant/ai/budget`

```json
{ "period":"2026-02", "budget_cost": 500, "hard_limit": true }
```

### AI用量报表

* `GET /api/admin/v1/tenant/ai/usage?from=2026-02-01&to=2026-02-27`
  返回：按 task_type、用户、项目、模型汇总 token/cost

---

## 4.5 集成配置（ERP/MES/钉钉）

### 端点与鉴权

* `GET /api/admin/v1/tenant/integrations`
* `POST /api/admin/v1/tenant/integrations`
* `POST /api/admin/v1/tenant/integrations/{id}/test_connection`

### Webhook订阅

* `POST /api/admin/v1/tenant/webhooks`
* `GET /api/admin/v1/tenant/webhooks/logs`

### 密钥轮换

* `POST /api/admin/v1/tenant/secrets/{id}/rotate`

---

## 4.6 审计与导出

* `GET /api/admin/v1/tenant/audit_logs?actor=&action=&from=&to=`
* `POST /api/admin/v1/tenant/exports`

```json
{ "job_type":"audit_export", "params": { "from":"2026-02-01","to":"2026-02-27" } }
```

---

# 5. 管理端 UI 页面清单（含布局要点）

## 5.1 平台级（Platform Admin）

1. 租户列表

* 筛选：状态/套餐/创建时间
* 行操作：进入租户、停用/启用、调整配额、查看用量

2. 租户详情

* 基本信息、套餐与配额、近30天用量、告警（AI超预算/存储超限）

3. 模型目录与价格策略

* model catalog（启用/禁用、单价、能力标签）

---

## 5.2 租户级（Tenant Admin）

1. 组织与用户

* 左：部门树；右：用户列表
* 用户详情：角色、主部门、状态、最近登录、API Key（可选）

2. 角色与权限

* 角色列表 + 权限点勾选矩阵

3. 流程与策略

* 阶段/Gate：可视化编辑（规则列表 + JSON 高级模式）
* 毛利红线：按范围（产品线/客户等级）配置
* 审批策略：条件 + 节点模板（负责人规则）

4. AI 治理

* 任务类型策略列表（demand_extract/quote_risk/contract_risk…）
* 月预算设置 + 用量统计图
* 风险：超预算、失败率、平均耗时、Top耗费用户/项目

5. 集成中心

* ERP/MES/钉钉/企微：连接参数、密钥、测试按钮
* Webhook：订阅事件、签名密钥、投递日志

6. 审计中心

* 操作审计：检索+导出
* 敏感操作快捷过滤：权限变更/密钥/附件下载/成本查看

---

# 6. 权限控制（管理端的权限点）

建议把管理端权限点单独划分 module：

* `admin.platform.*`（平台级）
* `admin.tenant.*`（租户级）
* `admin.tenant.iam.*`
* `admin.tenant.policy.*`
* `admin.tenant.ai.*`
* `admin.tenant.integration.*`
* `admin.tenant.audit.*`

**敏感操作强制二次确认（可选）**

* 修改配额、停用租户、查看密钥明文（默认禁止）、导出审计、修改字段脱敏

---

# 7. 关键安全要求（必须写进验收标准）

1. **tenant_id 强制隔离**（所有管理端接口必须校验 scope）
2. **密钥加密存储**（cipher_text + KMS/主密钥；至少应用层 AES-GCM）
3. **审计不可篡改**（追加写；导出留痕）
4. **AI 预算硬限制**（hard_limit=true 时拒绝新 AI 任务）
5. **策略更新要做 schema 校验**（gate_rules_json / ai_policy 输出 schema）
6. **权限变更即时生效**（缓存要可失效）

---

# 8. 初始化默认数据（租户开通时自动生成）

* 默认角色：sales/sales_mgr/tech/quote/finance/legal/service/admin
* 默认权限映射：最小可用
* 默认阶段定义 S1~S9 + Gate 规则（可简单起步）
* 默认毛利红线：按产品线（先一条全局）
* 默认审批策略：报价>某金额 或 毛利<红线 → 经理+财务审批
* 默认 AI 策略：仅在 S4 报价 / 合同审核触发，避免一上来烧钱

---

# 9. 开发任务拆解（可直接建任务）

## 9.1 后端

* tenant CRUD + plan/quota + status enforcement（中间件）
* iam：用户/部门/角色/权限点
* policy：stage/margin/approval/mask/secrecy CRUD + schema validator
* ai governance：policy/budget/rate-limit/usage 汇总
* integration：endpoint/secret/webhook/test_connection
* audit：log 写入拦截器 + 查询导出 job

## 9.2 前端

* 平台：租户列表/详情/配额编辑/用量图
* 租户：组织用户、角色权限、策略编辑器、AI治理、集成中心、审计中心
* 通用组件：JSON 编辑器（带 schema 校验）、部门树、权限矩阵、用量统计图表

---

# 10. 验收用例（建议你拿去做测试清单）

1. 新建租户 → 自动生成默认角色与策略 → 管理员可登录
2. 停用租户 → 业务端所有接口拒绝（403 tenant_suspended）
3. 配额覆盖生效：AI 月预算硬限制后，新 AI 任务创建被拒绝
4. 字段脱敏：普通销售查看报价版本时成本字段为 null；财务可见
5. RAG 权限继承：无权限用户无法通过 AI 检索到 restricted 文档
6. 密钥轮换：新密钥生效，旧密钥按策略失效，审计可追踪
7. 审计导出：导出任务生成文件，下载留痕
