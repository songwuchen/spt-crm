from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class InvoiceCreate(BaseModel):
    invoice_no: Optional[str] = Field(None, max_length=100)
    amount: Optional[float] = Field(None, ge=0)
    invoice_date: Optional[date] = None
    erp_ref_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=1000)


class InvoiceUpdate(BaseModel):
    amount: Optional[float] = Field(None, ge=0)
    invoice_date: Optional[date] = None
    status: Optional[str] = None
    erp_ref_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=1000)


class PaymentPlanCreate(BaseModel):
    plan_no: Optional[str] = Field(None, max_length=100)
    due_date: Optional[date] = None
    amount: Optional[float] = Field(None, ge=0)
    trigger_milestone_code: Optional[str] = Field(None, max_length=32)
    remark: Optional[str] = Field(None, max_length=1000)
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class PaymentPlanBulkCreate(BaseModel):
    plans: list[PaymentPlanCreate] = Field(default_factory=list)


class PaymentPlanUpdate(BaseModel):
    due_date: Optional[date] = None
    amount: Optional[float] = Field(None, ge=0)
    trigger_milestone_code: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=1000)
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class PaymentRecordCreate(BaseModel):
    received_date: Optional[date] = None
    amount: Optional[float] = Field(None, ge=0)
    channel: Optional[str] = Field(None, max_length=64)
    reference_no: Optional[str] = Field(None, max_length=100)
    matched_plan_id: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=1000)
