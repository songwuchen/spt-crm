from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re


LeadCategory = Literal["self_reported", "distributed"]
LeadCountryType = Literal["domestic", "overseas"]


def _validate_email(v: Optional[str]) -> Optional[str]:
    if v is not None and v != "" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
        raise ValueError("邮箱格式不正确")
    return v


class LeadCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    company_name: Optional[str] = Field(None, max_length=200)
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
    remark: Optional[str] = Field(None, max_length=2000)

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
    company_name: Optional[str] = Field(None, max_length=200)
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
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

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
    status: str
    score: int
    converted_customer_id: Optional[str] = None
    remark: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    model_config = {"from_attributes": True}
