from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


# ---------- Record ----------
class CommissionRecordCreate(BaseModel):
    record_no: Optional[str] = Field(None, max_length=64)
    project_id: Optional[str] = None
    contract_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=300)
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    department_id: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=100)
    signed_date: Optional[date] = None
    contract_amount: float = Field(0, ge=0)
    received_amount: float = Field(0, ge=0)
    deduction_freight: float = Field(0, ge=0)
    deduction_service: float = Field(0, ge=0)
    deduction_entertain: float = Field(0, ge=0)
    deduction_rebate: float = Field(0, ge=0)
    commission_rate: float = Field(0, ge=0, le=1)
    remark: Optional[str] = Field(None, max_length=2000)


class CommissionRecordUpdate(BaseModel):
    customer_name: Optional[str] = Field(None, max_length=300)
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    department_id: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=100)
    signed_date: Optional[date] = None
    contract_amount: Optional[float] = Field(None, ge=0)
    received_amount: Optional[float] = Field(None, ge=0)
    deduction_freight: Optional[float] = Field(None, ge=0)
    deduction_service: Optional[float] = Field(None, ge=0)
    deduction_entertain: Optional[float] = Field(None, ge=0)
    deduction_rebate: Optional[float] = Field(None, ge=0)
    commission_rate: Optional[float] = Field(None, ge=0, le=1)
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)


# ---------- Payout ----------
class CommissionPayoutCreate(BaseModel):
    paid_at: Optional[date] = None
    amount: float = Field(..., gt=0)
    method: Optional[str] = Field(None, max_length=64)
    remark: Optional[str] = Field(None, max_length=1000)


# ---------- Rule ----------
class CommissionRuleCreate(BaseModel):
    name: str = Field(..., max_length=200)
    scope_type: str = Field("all", max_length=16)
    department_id: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=100)
    rate: float = Field(0, ge=0, le=1)
    min_amount: Optional[float] = Field(None, ge=0)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = Field(None, max_length=1000)


class CommissionRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    scope_type: Optional[str] = Field(None, max_length=16)
    department_id: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=100)
    rate: Optional[float] = Field(None, ge=0, le=1)
    min_amount: Optional[float] = Field(None, ge=0)
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None
    remark: Optional[str] = Field(None, max_length=1000)
