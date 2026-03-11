from typing import Optional, List
from pydantic import BaseModel, Field


class QuoteCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    validity_days: Optional[int] = Field(30, ge=1, le=365)
    terms_summary_json: Optional[dict] = None


class QuoteUpdate(BaseModel):
    status: Optional[str] = None


class QuoteVersionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    tax_rate: Optional[float] = Field(None, ge=0, le=1)
    discount_total: Optional[float] = Field(None, ge=0)
    delivery_promise_date: Optional[str] = None
    validity_days: Optional[int] = Field(None, ge=1, le=365)
    terms_summary_json: Optional[dict] = None
    status: Optional[str] = None


class QuoteLineCreate(BaseModel):
    item_type: Optional[str] = None
    item_name: Optional[str] = Field(None, max_length=200)
    item_code: Optional[str] = Field(None, max_length=100)
    spec: Optional[str] = Field(None, max_length=500)
    qty: Optional[float] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[float] = Field(None, ge=0)
    cost_est: Optional[float] = Field(None, ge=0)
    leadtime_days: Optional[int] = Field(None, ge=0)


class QuoteLineUpdate(BaseModel):
    item_type: Optional[str] = None
    item_name: Optional[str] = Field(None, max_length=200)
    item_code: Optional[str] = Field(None, max_length=100)
    spec: Optional[str] = Field(None, max_length=500)
    qty: Optional[float] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[float] = Field(None, ge=0)
    cost_est: Optional[float] = Field(None, ge=0)
    leadtime_days: Optional[int] = Field(None, ge=0)


class CostSnapshotCreate(BaseModel):
    note: Optional[str] = Field(None, max_length=500)
    snapshot_type: Optional[str] = Field("manual", pattern=r"^(manual|auto|approval)$")
    breakdown_json: Optional[dict] = None  # {material, processing, outsource, install, transport, admin, risk}


class QuoteSendLogCreate(BaseModel):
    channel: str = Field(..., pattern=r"^(email|wechat|print|other)$")
    to_list_json: Optional[list] = None  # [{name, contact}]
    subject: Optional[str] = Field(None, max_length=300)
    body: Optional[str] = None
    attachments_json: Optional[list] = None  # [{filename, attachment_id}]
