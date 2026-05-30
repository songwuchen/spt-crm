from typing import Optional
from datetime import date
from pydantic import BaseModel, Field, field_validator

_STATUSES = ("preparing", "submitted", "won", "lost", "cancelled")


class TenderCreate(BaseModel):
    customer_id: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=300)
    bid_amount: Optional[float] = Field(None, ge=0)
    budget_amount: Optional[float] = Field(None, ge=0)
    status: Optional[str] = "preparing"
    submit_date: Optional[date] = None
    open_date: Optional[date] = None
    result: Optional[str] = Field(None, max_length=300)
    owner_id: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _STATUSES:
            raise ValueError(f"状态必须为 {'/'.join(_STATUSES)}")
        return v


class TenderUpdate(BaseModel):
    project_id: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    bid_amount: Optional[float] = Field(None, ge=0)
    budget_amount: Optional[float] = Field(None, ge=0)
    status: Optional[str] = None
    submit_date: Optional[date] = None
    open_date: Optional[date] = None
    result: Optional[str] = Field(None, max_length=300)
    owner_id: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _STATUSES:
            raise ValueError(f"状态必须为 {'/'.join(_STATUSES)}")
        return v
