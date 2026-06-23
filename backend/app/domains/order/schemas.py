from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field, field_validator

_STATUSES = ("draft", "confirmed", "producing", "shipped", "completed", "cancelled")


class OrderLineIn(BaseModel):
    product_id: Optional[str] = None
    product_name: str = Field(..., min_length=1, max_length=300)
    spec: Optional[str] = Field(None, max_length=200)
    unit: Optional[str] = Field(None, max_length=32)
    quantity: float = Field(0, ge=0)
    unit_price: float = Field(0, ge=0)


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
    lines: Optional[List[OrderLineIn]] = None

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
    lines: Optional[List[OrderLineIn]] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _STATUSES:
            raise ValueError(f"状态必须为 {'/'.join(_STATUSES)}")
        return v


class OrderShipItem(BaseModel):
    line_id: str
    ship_quantity: float = Field(..., ge=0)


class OrderShip(BaseModel):
    """发货：传 items 按行登记本次发货数量；或 full=True 一键全部发货。"""
    full: bool = False
    items: Optional[List[OrderShipItem]] = None
