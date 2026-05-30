from typing import Optional
from pydantic import BaseModel


class ChangeRequestCreate(BaseModel):
    change_type: str
    reason: Optional[str] = None
    from_version_ref_json: Optional[dict] = None
    impact_json: Optional[dict] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class ChangeRequestUpdate(BaseModel):
    reason: Optional[str] = None
    from_version_ref_json: Optional[dict] = None
    to_version_ref_json: Optional[dict] = None
    impact_json: Optional[dict] = None
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
