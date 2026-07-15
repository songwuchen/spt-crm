from typing import Literal, Optional, List
from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator
import re


LeadCategory = Literal["self_reported", "distributed"]
LeadCountryType = Literal["domestic", "overseas"]


class LeadProductIn(BaseModel):
    """线索产品明细(子表)一行。"""
    product_name: Optional[str] = Field(None, max_length=300)
    product_spec: Optional[str] = Field(None, max_length=300)
    quantity: Optional[float] = Field(None, ge=0)
    remark: Optional[str] = Field(None, max_length=2000)


class LeadProductOut(LeadProductIn):
    id: str
    model_config = {"from_attributes": True}


def _validate_email(v: Optional[str]) -> Optional[str]:
    if v is not None and v != "" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
        raise ValueError("邮箱格式不正确")
    return v


class LeadCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    company_name: str = Field(..., min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[str] = Field(None, max_length=200)
    contact_raw_json: Optional[dict] = None
    source: Optional[str] = None
    source_detail_json: Optional[dict] = None
    demand_summary: Optional[str] = Field(None, max_length=2000)
    industry: Optional[str] = None
    customer_type: Optional[str] = Field(None, max_length=50)
    category: Optional[LeadCategory] = None
    country_type: Optional[LeadCountryType] = None
    country_name: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    department_id: Optional[str] = Field(None, max_length=36)
    budget_range: Optional[str] = None
    owner_id: Optional[str] = Field(None, max_length=36)
    biz_date: Optional[date] = None
    remark: Optional[str] = Field(None, max_length=2000)
    products: Optional[List[LeadProductIn]] = None
    custom_fields_json: Optional[dict] = None

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)

    @model_validator(mode="after")
    def _country_name_only_when_overseas(self):
        # Guard against stale country_name sticking around after switching back to domestic
        if self.country_type != "overseas":
            self.country_name = None
        return self


class LeadUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    company_name: Optional[str] = Field(None, min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[str] = Field(None, max_length=200)
    contact_raw_json: Optional[dict] = None
    source: Optional[str] = None
    source_detail_json: Optional[dict] = None
    demand_summary: Optional[str] = Field(None, max_length=2000)
    industry: Optional[str] = None
    customer_type: Optional[str] = Field(None, max_length=50)
    category: Optional[LeadCategory] = None
    country_type: Optional[LeadCountryType] = None
    country_name: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    department_id: Optional[str] = Field(None, max_length=36)
    budget_range: Optional[str] = None
    owner_id: Optional[str] = Field(None, max_length=36)
    biz_date: Optional[date] = None
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)
    products: Optional[List[LeadProductIn]] = None
    custom_fields_json: Optional[dict] = None

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        return _validate_email(v)


class LeadOut(BaseModel):
    id: str
    title: str
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_raw_json: Optional[dict] = None
    source: Optional[str] = None
    source_detail_json: Optional[dict] = None
    demand_summary: Optional[str] = None
    industry: Optional[str] = None
    customer_type: Optional[str] = None
    category: Optional[str] = None
    country_type: Optional[str] = None
    country_name: Optional[str] = None
    region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    department_id: Optional[str] = None
    budget_range: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    biz_date: Optional[str] = None
    status: str
    review_status: str = "approved"
    review_flow_id: Optional[str] = None
    reject_reason: Optional[str] = None
    score: int
    converted_customer_id: Optional[str] = None
    remark: Optional[str] = None
    custom_fields_json: Optional[dict] = None
    products: List[LeadProductOut] = []
    created_at: str = ""
    updated_at: str = ""

    model_config = {"from_attributes": True}
