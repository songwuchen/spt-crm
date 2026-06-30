from sqlalchemy import String, Text, JSON, Integer, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase, PlatformBase


# ==================== Platform Level ====================

class TenantPlan(PlatformBase):
    """套餐定义"""
    __tablename__ = "tenant_plans"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    pricing_json: Mapped[dict | None] = mapped_column(JSON)
    limits_json: Mapped[dict | None] = mapped_column(JSON)
    # {"user_seats": 100, "storage_gb": 500, "ai_monthly_tokens": 20000000, "ai_monthly_cost": 300}
    features_json: Mapped[dict | None] = mapped_column(JSON)
    # {"ai_center": true, "rag": true, "contract_risk": true}
    status: Mapped[str] = mapped_column(String(16), default="active")


class TenantUsageMeter(PlatformBase):
    """用量计量"""
    __tablename__ = "tenant_usage_meters"

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False)
    # user_active / ai_tokens / ai_cost / storage_bytes / api_calls
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM
    value: Mapped[float] = mapped_column(Numeric(18, 4), default=0)


# ==================== Tenant Level ====================

class TenantProfile(TenantScopedBase):
    """租户配置"""
    __tablename__ = "tenant_profiles"

    timezone: Mapped[str | None] = mapped_column(String(64), default="Asia/Shanghai")
    locale: Mapped[str | None] = mapped_column(String(16), default="zh-CN")
    logo_attachment_id: Mapped[str | None] = mapped_column(String(36))
    security_policy_json: Mapped[dict | None] = mapped_column(JSON)
    data_retention_days: Mapped[int | None] = mapped_column(Integer, default=365)
    # ---- 界面个性化（界面设置）----
    system_name: Mapped[str | None] = mapped_column(String(64))      # 系统显示名（品牌名），空=默认
    menu_aliases_json: Mapped[dict | None] = mapped_column(JSON)     # {菜单key: 别名}
    hidden_menus_json: Mapped[list | None] = mapped_column(JSON)     # 隐藏的菜单key列表


class TenantFeatureToggle(TenantScopedBase):
    """功能开关"""
    __tablename__ = "tenant_feature_toggles"

    feature_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict | None] = mapped_column(JSON)


class StageDefinition(TenantScopedBase):
    """阶段与Gate配置"""
    __tablename__ = "stage_definitions"

    stage_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    allowed_transitions_json: Mapped[dict | None] = mapped_column(JSON)
    gate_rules_json: Mapped[dict | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MarginPolicy(TenantScopedBase):
    """毛利红线策略"""
    __tablename__ = "margin_policies"

    policy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_json: Mapped[dict | None] = mapped_column(JSON)
    # {"product_line":"激光切割","customer_level":"A"}
    redline_rate: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    action: Mapped[str] = mapped_column(String(32), default="warn")
    # block / need_approval / warn
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TenantAiPolicy(TenantScopedBase):
    """AI策略"""
    __tablename__ = "tenant_ai_policies"

    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_route_json: Mapped[dict | None] = mapped_column(JSON)
    budget_json: Mapped[dict | None] = mapped_column(JSON)
    trigger_json: Mapped[dict | None] = mapped_column(JSON)
    guardrails_json: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TenantAiBudget(TenantScopedBase):
    """AI月度预算"""
    __tablename__ = "tenant_ai_budgets"

    period: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM
    budget_cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    used_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), default=0)
    budget_tokens: Mapped[int | None] = mapped_column(Integer)
    used_tokens: Mapped[int | None] = mapped_column(Integer, default=0)
    hard_limit: Mapped[bool] = mapped_column(Boolean, default=False)


class ApprovalPolicy(TenantScopedBase):
    """审批策略配置"""
    __tablename__ = "approval_policies"

    biz_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # quote_version / contract_version / change_request
    name: Mapped[str | None] = mapped_column(String(200))
    condition_json: Mapped[dict | None] = mapped_column(JSON)
    # {"margin_rate_lt": 0.25, "amount_gt": 100000}
    approver_rules_json: Mapped[dict | None] = mapped_column(JSON)
    # [{"type": "role", "value": "finance_manager"}, {"type": "user_field", "value": "owner.department.manager"}]
    approval_mode: Mapped[str] = mapped_column(String(32), default="sequential")
    # sequential | parallel | any_one
    sla_hours: Mapped[int | None] = mapped_column(Integer)
    escalation_json: Mapped[dict | None] = mapped_column(JSON)
    # [{"after_hours": 24, "action": "remind"}, {"after_hours": 48, "action": "auto_approve"}]
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class DocTemplate(TenantScopedBase):
    """文档模板（报价/合同）"""
    __tablename__ = "doc_templates"

    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # quote / contract
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    content_json: Mapped[dict | None] = mapped_column(JSON)
    # For quote: {title, terms_summary_json, tax_rate, validity_days, lines: [{item_name,spec,qty,unit,unit_price,...}]}
    # For contract: {title, payment_terms_json, delivery_terms_json, key_clauses_json}
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class EmailTemplate(TenantScopedBase):
    """邮件模板"""
    __tablename__ = "email_templates"

    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # follow_up_reminder / contract_expiry / approval_notify / payment_overdue / quote_sent
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500))
    body_html: Mapped[str | None] = mapped_column(Text)
    variables_json: Mapped[dict | None] = mapped_column(JSON)
    # [{name: "customer_name", label: "客户名称"}, ...]
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class CustomFieldDef(TenantScopedBase):
    """自定义字段定义"""
    __tablename__ = "custom_field_defs"

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # customer / project / lead / contact / service_ticket
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    field_label: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # text / number / date / select / multiselect / boolean
    options_json: Mapped[dict | None] = mapped_column(JSON)
    # for select/multiselect: ["option1", "option2"]
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class DataDictionary(TenantScopedBase):
    """数据字典 — 可配置的下拉选项"""
    __tablename__ = "data_dictionaries"

    dict_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # industry / customer_source / customer_level / risk_level / ticket_category ...
    dict_code: Mapped[str] = mapped_column(String(64), nullable=False)
    dict_label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(32))
    extra_json: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class IntegrationEndpoint(TenantScopedBase):
    """集成端点配置"""
    __tablename__ = "integration_endpoints"

    system_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # erp_k3 / mes_xxx / dingtalk / wecom
    name: Mapped[str | None] = mapped_column(String(200))
    base_url: Mapped[str | None] = mapped_column(String(500))
    auth_type: Mapped[str | None] = mapped_column(String(32))
    # apikey / oauth2 / basic
    auth_config_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="active")


class WebhookSubscription(TenantScopedBase):
    """Webhook订阅"""
    __tablename__ = "webhook_subscriptions"

    event_types_json: Mapped[dict | None] = mapped_column(JSON)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret_token: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="active")


class TenantStorageConfig(TenantScopedBase):
    """文件存储配置 — 选择本地 / MinIO / 阿里云OSS"""
    __tablename__ = "tenant_storage_configs"

    storage_type: Mapped[str] = mapped_column(String(16), default="local")
    # local / minio / oss
    config_json: Mapped[dict | None] = mapped_column(JSON)
    # 按 provider 命名空间保存各后端凭证，切换后端不丢失历史配置：
    # {"minio": {"endpoint": "host:port", "access_key": "...", "secret_key": "enc:...",
    #            "bucket": "...", "secure": false},
    #  "oss":   {"endpoint": "https://oss-cn-hangzhou.aliyuncs.com", "access_key": "...",
    #            "secret_key": "enc:...", "bucket": "..."}}
