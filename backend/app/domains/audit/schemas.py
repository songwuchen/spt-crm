from typing import Optional
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    summary: Optional[str] = None
    detail: Optional[dict] = None
    ip: Optional[str] = None
    created_at: str = ""

    model_config = {"from_attributes": True}
