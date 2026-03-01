from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


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
    region: Optional[str] = Field(None, max_length=100)
    budget_range: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("邮箱格式不正确")
        return v


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
    region: Optional[str] = Field(None, max_length=100)
    budget_range: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("邮箱格式不正确")
        return v


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
    region: Optional[str] = None
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
