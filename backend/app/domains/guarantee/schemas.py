from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class GuaranteeCreate(BaseModel):
    guarantee_no: Optional[str] = Field(None, max_length=64)
    type: str = Field("performance", max_length=24)
    direction: str = Field("outgoing", max_length=16)
    contract_id: Optional[str] = None
    project_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=300)
    amount: Optional[float] = Field(None, ge=0)
    issuer: Optional[str] = Field(None, max_length=200)
    fee: Optional[float] = Field(None, ge=0)
    rate: Optional[float] = Field(None, ge=0, le=1)
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = Field(None, max_length=2000)


class GuaranteeUpdate(BaseModel):
    type: Optional[str] = Field(None, max_length=24)
    direction: Optional[str] = Field(None, max_length=16)
    contract_id: Optional[str] = None
    project_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=300)
    amount: Optional[float] = Field(None, ge=0)
    issuer: Optional[str] = Field(None, max_length=200)
    fee: Optional[float] = Field(None, ge=0)
    rate: Optional[float] = Field(None, ge=0, le=1)
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=100)
    remark: Optional[str] = Field(None, max_length=2000)


class GuaranteeReturn(BaseModel):
    return_date: Optional[date] = None
    remark: Optional[str] = Field(None, max_length=2000)
