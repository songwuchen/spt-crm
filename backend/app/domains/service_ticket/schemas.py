from typing import Optional
from pydantic import BaseModel


class ServiceTicketCreate(BaseModel):
    customer_id: Optional[str] = None
    project_id: Optional[str] = None
    type: str
    priority: Optional[str] = "medium"
    description: Optional[str] = None
    assigned_to_id: Optional[str] = None
    assigned_to_name: Optional[str] = None


class ServiceTicketUpdate(BaseModel):
    type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    resolution: Optional[str] = None
    assigned_to_id: Optional[str] = None
    assigned_to_name: Optional[str] = None


class RenewalCreate(BaseModel):
    customer_id: str
    name: str
    amount_expect: Optional[float] = None
    close_date_expect: Optional[str] = None
    probability: Optional[int] = None
    related_asset_json: Optional[dict] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    remark: Optional[str] = None


class RenewalUpdate(BaseModel):
    name: Optional[str] = None
    amount_expect: Optional[float] = None
    close_date_expect: Optional[str] = None
    probability: Optional[int] = None
    related_asset_json: Optional[dict] = None
    status: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    remark: Optional[str] = None
