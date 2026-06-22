from pydantic import BaseModel
from typing import Optional, Union


# ---- Platform ----
class TenantPlanCreate(BaseModel):
    name: str
    limits_json: Optional[dict] = None
    features_json: Optional[dict] = None
    pricing_json: Optional[dict] = None

class TenantPlanUpdate(BaseModel):
    name: Optional[str] = None
    limits_json: Optional[dict] = None
    features_json: Optional[dict] = None
    pricing_json: Optional[dict] = None
    status: Optional[str] = None

class PlatformTenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    plan_id: Optional[str] = None

# ---- Tenant Profile ----
class TenantProfileUpdate(BaseModel):
    timezone: Optional[str] = None
    locale: Optional[str] = None
    logo_attachment_id: Optional[str] = None
    security_policy_json: Optional[dict] = None
    data_retention_days: Optional[int] = None

# ---- Feature Toggle ----
class FeatureToggleUpdate(BaseModel):
    enabled: Optional[bool] = None
    config_json: Optional[dict] = None

# ---- Stage Definition ----
class StageDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    # 这两个字段实际存的是数组（阶段流转列表 / Gate 规则列表），早先误标为 dict
    # 导致前端保存 Gate 规则时 422。
    allowed_transitions_json: Optional[Union[dict, list]] = None
    gate_rules_json: Optional[Union[dict, list]] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None

# ---- Margin Policy ----
class MarginPolicyCreate(BaseModel):
    policy_code: str
    scope_json: Optional[dict] = None
    redline_rate: float
    action: Optional[str] = "warn"

class MarginPolicyUpdate(BaseModel):
    scope_json: Optional[dict] = None
    redline_rate: Optional[float] = None
    action: Optional[str] = None
    enabled: Optional[bool] = None

# ---- AI Policy ----
class AiPolicyUpdate(BaseModel):
    model_route_json: Optional[dict] = None
    budget_json: Optional[dict] = None
    trigger_json: Optional[dict] = None
    guardrails_json: Optional[dict] = None
    enabled: Optional[bool] = None

# ---- AI Budget ----
class AiBudgetUpdate(BaseModel):
    period: str
    budget_cost: Optional[float] = None
    budget_tokens: Optional[int] = None
    hard_limit: Optional[bool] = None

# ---- Approval Policy ----
class ApprovalPolicyCreate(BaseModel):
    biz_type: str
    name: Optional[str] = None
    condition_json: Optional[Union[dict, list]] = None
    approver_rules_json: Optional[Union[dict, list]] = None
    approval_mode: Optional[str] = "sequential"
    sla_hours: Optional[int] = None
    escalation_json: Optional[list] = None
    priority: Optional[int] = 0

class ApprovalPolicyUpdate(BaseModel):
    name: Optional[str] = None
    condition_json: Optional[Union[dict, list]] = None
    approver_rules_json: Optional[Union[dict, list]] = None
    approval_mode: Optional[str] = None
    sla_hours: Optional[int] = None
    escalation_json: Optional[list] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None

# ---- Integration ----
class IntegrationCreate(BaseModel):
    system_code: str
    name: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config_json: Optional[dict] = None

class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config_json: Optional[dict] = None
    status: Optional[str] = None

# ---- Webhook ----
class WebhookCreate(BaseModel):
    event_types_json: Optional[Union[dict, list]] = None
    target_url: str
    secret_token: Optional[str] = None

# ---- File Storage ----
class StorageProviderConfig(BaseModel):
    """单个存储后端的连接配置（minio / oss）"""
    endpoint: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None
    secure: Optional[bool] = None  # MinIO 是否启用 https
    public_base_url: Optional[str] = None  # 可选：直链下载基址

class StorageConfigUpdate(BaseModel):
    storage_type: str  # local / minio / oss
    minio: Optional[StorageProviderConfig] = None
    oss: Optional[StorageProviderConfig] = None
