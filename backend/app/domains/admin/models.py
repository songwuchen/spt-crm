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
