from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContractReviewCreate(BaseModel):
    review_type: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field("draft", max_length=24)
    customer_id: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=300)
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    department_id: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=200)
    region_manager_id: Optional[str] = None
    region_manager_name: Optional[str] = Field(None, max_length=100)
    is_export: Optional[str] = Field(None, max_length=16)
    need_pricing: Optional[str] = Field(None, max_length=32)
    need_install: Optional[str] = Field(None, max_length=64)
    customer_type: Optional[str] = Field(None, max_length=32)
    elec_ctrl: Optional[str] = Field(None, max_length=64)
    project_title: Optional[str] = None
    reported_at: Optional[datetime] = None
    contract_amount: Optional[float] = None
    delivery_period: Optional[str] = Field(None, max_length=200)
    conclusion: Optional[str] = None
    payment_term: Optional[str] = Field(None, max_length=200)
    review_json: Optional[dict[str, Any]] = None


class ContractReviewUpdate(BaseModel):
    review_type: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field(None, max_length=24)
    customer_id: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=300)
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    department_id: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=200)
    region_manager_id: Optional[str] = None
    region_manager_name: Optional[str] = Field(None, max_length=100)
    is_export: Optional[str] = Field(None, max_length=16)
    need_pricing: Optional[str] = Field(None, max_length=32)
    need_install: Optional[str] = Field(None, max_length=64)
    customer_type: Optional[str] = Field(None, max_length=32)
    elec_ctrl: Optional[str] = Field(None, max_length=64)
    project_title: Optional[str] = None
    reported_at: Optional[datetime] = None
    contract_amount: Optional[float] = None
    delivery_period: Optional[str] = Field(None, max_length=200)
    conclusion: Optional[str] = None
    payment_term: Optional[str] = Field(None, max_length=200)
    review_json: Optional[dict[str, Any]] = None
