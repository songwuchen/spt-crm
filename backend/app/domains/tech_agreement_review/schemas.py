from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TechAgreementReviewCreate(BaseModel):
    status: Optional[str] = Field("draft", max_length=24)
    customer_id: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=300)
    applicant_id: Optional[str] = None
    applicant_name: Optional[str] = Field(None, max_length=100)
    apply_at: Optional[datetime] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    department_id: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    elec_ctrl: Optional[str] = Field(None, max_length=64)
    project_title: Optional[str] = None
    has_weight_req: Optional[str] = Field(None, max_length=16)
    use_idle_equip: Optional[str] = Field(None, max_length=16)
    has_smart: Optional[str] = Field(None, max_length=16)
    need_pricing: Optional[str] = Field(None, max_length=32)
    sign_basis: Optional[str] = Field(None, max_length=500)
    ref_contract_no: Optional[str] = Field(None, max_length=200)
    pre_contact: Optional[str] = Field(None, max_length=200)
    remark: Optional[str] = None
    has_objection: Optional[str] = Field(None, max_length=16)
    form_json: Optional[dict[str, Any]] = None


class TechAgreementReviewUpdate(TechAgreementReviewCreate):
    status: Optional[str] = Field(None, max_length=24)
