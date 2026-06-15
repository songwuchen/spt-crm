from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# Full catalogue of scopes an app can be granted.
ALL_SCOPES = [
    "crm.customer.read",
    "crm.contact.read",
    "crm.project.read",
    "crm.contract.read",
    "crm.quote.read",
    "crm.order.read",
    "crm.payment.read",
    "crm.product.read",
    "crm.service.read",
    "crm.delivery.read",
    "crm.event.read",
    # write scopes (require Idempotency-Key)
    "crm.lead.write",
    "crm.activity.write",
    "crm.customer.write",
    "crm.service.write",
]

_ACTIVITY_BIZ_TYPES = {"customer", "project", "lead"}


class OpenLeadCreate(BaseModel):
    """External lead-intake payload for POST /openapi/v1/leads."""
    title: str = Field(..., min_length=1, max_length=200)
    company_name: str = Field(..., min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[str] = Field(None, max_length=200)
    source: Optional[str] = Field(None, max_length=100)
    demand_summary: Optional[str] = Field(None, max_length=2000)
    industry: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    budget_range: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = Field(None, max_length=2000)


class OpenActivityCreate(BaseModel):
    """External follow-up / activity record for POST /openapi/v1/activities."""
    biz_type: str = Field(..., description="customer / project / lead")
    biz_id: str = Field(..., max_length=36)
    activity_type: str = Field("note", max_length=32)  # call/visit/meeting/email/note
    subject: Optional[str] = Field(None, max_length=300)
    content: Optional[str] = Field(None, max_length=4000)
    next_follow_date: Optional[str] = None

    @field_validator("biz_type")
    @classmethod
    def _check_biz_type(cls, v: str) -> str:
        if v not in _ACTIVITY_BIZ_TYPES:
            raise ValueError(f"biz_type must be one of {sorted(_ACTIVITY_BIZ_TYPES)}")
        return v


class OpenCustomerCreate(BaseModel):
    """External customer-intake payload for POST /openapi/v1/customers."""
    name: str = Field(..., min_length=1, max_length=200)
    short_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = Field(None, max_length=100)
    level: Optional[str] = Field(None, max_length=8)
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("level")
    @classmethod
    def _check_level(cls, v):
        if v is not None and v not in ("A", "B", "C", "D"):
            raise ValueError("level 必须为 A/B/C/D")
        return v


class OpenServiceTicketCreate(BaseModel):
    """External support-ticket intake for POST /openapi/v1/service-tickets."""
    type: str = Field(..., max_length=32, description="fault/maintenance/training/spare/upgrade")
    customer_id: Optional[str] = Field(None, max_length=36)
    project_id: Optional[str] = Field(None, max_length=36)
    priority: Optional[str] = Field("medium", max_length=16)  # low/medium/high/critical
    description: Optional[str] = Field(None, max_length=4000)

_AUTH_MODES = {"apikey", "hmac"}
_STATUSES = {"enabled", "disabled"}


class OpenApiAppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    app_type: str = Field("external_system", max_length=64)
    auth_mode: str = "apikey"
    scopes: List[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(600, ge=1, le=100000)
    ip_whitelist: Optional[List[str]] = None
    remark: Optional[str] = Field(None, max_length=500)

    @field_validator("auth_mode")
    @classmethod
    def _check_auth_mode(cls, v: str) -> str:
        if v not in _AUTH_MODES:
            raise ValueError(f"auth_mode must be one of {sorted(_AUTH_MODES)}")
        return v

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, v: List[str]) -> List[str]:
        bad = [s for s in v if s not in ALL_SCOPES]
        if bad:
            raise ValueError(f"unknown scopes: {bad}")
        return v


class OpenApiAppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    status: Optional[str] = None
    auth_mode: Optional[str] = None
    scopes: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=100000)
    ip_whitelist: Optional[List[str]] = None
    remark: Optional[str] = Field(None, max_length=500)

    @field_validator("status")
    @classmethod
    def _check_status(cls, v):
        if v is not None and v not in _STATUSES:
            raise ValueError(f"status must be one of {sorted(_STATUSES)}")
        return v

    @field_validator("auth_mode")
    @classmethod
    def _check_auth_mode(cls, v):
        if v is not None and v not in _AUTH_MODES:
            raise ValueError(f"auth_mode must be one of {sorted(_AUTH_MODES)}")
        return v

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, v):
        if v is not None:
            bad = [s for s in v if s not in ALL_SCOPES]
            if bad:
                raise ValueError(f"unknown scopes: {bad}")
        return v
