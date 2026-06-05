from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class EquipmentCreate(BaseModel):
    customer_id: str
    customer_name: Optional[str] = Field(None, max_length=300)
    name: str = Field(..., max_length=200)
    category: Optional[str] = Field(None, max_length=64)
    spec: Optional[str] = Field(None, max_length=200)
    supplier: Optional[str] = Field(None, max_length=200)
    is_competitor: bool = False
    usage_years: Optional[float] = Field(None, ge=0)
    quantity: Optional[int] = Field(None, ge=0)
    condition: Optional[str] = Field(None, max_length=2000)
    replace_plan_date: Optional[date] = None
    spare_usage: Optional[str] = Field(None, max_length=2000)
    remark: Optional[str] = Field(None, max_length=2000)


class EquipmentUpdate(BaseModel):
    customer_name: Optional[str] = Field(None, max_length=300)
    name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=64)
    spec: Optional[str] = Field(None, max_length=200)
    supplier: Optional[str] = Field(None, max_length=200)
    is_competitor: Optional[bool] = None
    usage_years: Optional[float] = Field(None, ge=0)
    quantity: Optional[int] = Field(None, ge=0)
    condition: Optional[str] = Field(None, max_length=2000)
    replace_plan_date: Optional[date] = None
    spare_usage: Optional[str] = Field(None, max_length=2000)
    remark: Optional[str] = Field(None, max_length=2000)


class EquipmentToRenewal(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    amount_expect: Optional[float] = Field(None, ge=0)
    close_date_expect: Optional[date] = None
    remark: Optional[str] = Field(None, max_length=2000)


class SurveyCreate(BaseModel):
    customer_id: str
    customer_name: Optional[str] = Field(None, max_length=300)
    industry: Optional[str] = Field(None, max_length=64)
    main_products: Optional[str] = Field(None, max_length=300)
    annual_output: Optional[str] = Field(None, max_length=100)
    branch_info: Optional[str] = Field(None, max_length=4000)
    process_desc: Optional[str] = Field(None, max_length=4000)
    pain_points: Optional[str] = Field(None, max_length=4000)
    survey_date: Optional[date] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = Field(None, max_length=2000)


class SurveyUpdate(BaseModel):
    industry: Optional[str] = Field(None, max_length=64)
    main_products: Optional[str] = Field(None, max_length=300)
    annual_output: Optional[str] = Field(None, max_length=100)
    branch_info: Optional[str] = Field(None, max_length=4000)
    process_desc: Optional[str] = Field(None, max_length=4000)
    pain_points: Optional[str] = Field(None, max_length=4000)
    survey_date: Optional[date] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = Field(None, max_length=2000)
