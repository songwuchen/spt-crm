from datetime import date
from typing import Optional
from pydantic import BaseModel


class ErpOrderLinkCreate(BaseModel):
    erp_system_code: Optional[str] = None
    erp_order_no: Optional[str] = None
    remark: Optional[str] = None


class ErpOrderLinkUpdate(BaseModel):
    erp_system_code: Optional[str] = None
    erp_order_no: Optional[str] = None
    sync_status: Optional[str] = None
    remark: Optional[str] = None


class MilestoneCreate(BaseModel):
    milestone_code: str
    name: Optional[str] = None
    plan_date: Optional[date] = None
    sort_order: Optional[int] = 0
    note: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class MilestoneUpdate(BaseModel):
    name: Optional[str] = None
    plan_date: Optional[date] = None
    actual_date: Optional[date] = None
    status: Optional[str] = None
    source_type: Optional[str] = None
    sort_order: Optional[int] = None
    note: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
