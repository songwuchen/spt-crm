from typing import Optional
from datetime import date
from pydantic import BaseModel, Field, field_validator

_STATUSES = ("draft", "confirmed", "producing", "shipped", "completed", "cancelled")


class OrderCreate(BaseModel):
    customer_id: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    contract_id: Optional[str] = None
    title: Optional[str] = Field(None, max_length=300)
    amount: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = "CNY"
    status: Optional[str] = "draft"
    order_date: Optional[date] = None
    delivery_date: Optional[date] = None
    owner_id: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _STATUSES:
            raise ValueError(f"状态必须为 {'/'.join(_STATUSES)}")
        return v


class OrderUpdate(BaseModel):
    project_id: Optional[str] = None
    contract_id: Optional[str] = None
    title: Optional[str] = Field(None, max_length=300)
    amount: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = None
    status: Optional[str] = None
    order_date: Optional[date] = None
    delivery_date: Optional[date] = None
    owner_id: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _STATUSES:
            raise ValueError(f"状态必须为 {'/'.join(_STATUSES)}")
        return v
