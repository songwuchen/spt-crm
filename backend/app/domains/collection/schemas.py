from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class DebtTransferCreate(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=300)
    transfer_type: str = Field("sales_to_collection", max_length=32)
    from_department_id: Optional[str] = None
    from_department_name: Optional[str] = Field(None, max_length=100)
    from_owner_id: Optional[str] = None
    from_owner_name: Optional[str] = Field(None, max_length=100)
    to_department_id: Optional[str] = None
    to_department_name: Optional[str] = Field(None, max_length=100)
    debt_amount: Optional[float] = Field(None, ge=0)
    contact: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=64)
    debt_note: Optional[str] = Field(None, max_length=4000)
    reason: Optional[str] = Field(None, max_length=4000)
    deadline: Optional[date] = None
    assess_date: Optional[date] = None


class DebtTransferUpdate(BaseModel):
    customer_name: Optional[str] = Field(None, max_length=300)
    transfer_type: Optional[str] = Field(None, max_length=32)
    to_department_id: Optional[str] = None
    to_department_name: Optional[str] = Field(None, max_length=100)
    debt_amount: Optional[float] = Field(None, ge=0)
    contact: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=64)
    debt_note: Optional[str] = Field(None, max_length=4000)
    reason: Optional[str] = Field(None, max_length=4000)
    deadline: Optional[date] = None
    assess_date: Optional[date] = None
    status: Optional[str] = None


class DebtTransferClaim(BaseModel):
    """抢单接收。"""
    commitment: Optional[str] = Field(None, max_length=2000)
    claimed_department_id: Optional[str] = None
    claimed_department_name: Optional[str] = Field(None, max_length=100)


class CollectionFollowUpCreate(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=300)
    transfer_id: Optional[str] = None
    follow_date: Optional[date] = None
    method: Optional[str] = Field(None, max_length=32)
    feedback: Optional[str] = Field(None, max_length=4000)
    expected_date: Optional[date] = None
    amount_promised: Optional[float] = Field(None, ge=0)
    next_action: Optional[str] = Field(None, max_length=2000)
