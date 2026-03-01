from typing import Optional
from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    code: str
    plan: str = "free"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    remark: Optional[str] = None


class TenantOut(BaseModel):
    id: str
    name: str
    code: str
    plan: str
    is_active: bool
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    remark: Optional[str] = None

    model_config = {"from_attributes": True}


class TenantStatusUpdate(BaseModel):
    is_active: bool
