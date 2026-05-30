from typing import Optional
from pydantic import BaseModel


class SolutionCreate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    config_json: Optional[dict] = None
    risk_list_json: Optional[dict] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class SolutionUpdate(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class SolutionVersionUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    config_json: Optional[dict] = None
    risk_list_json: Optional[dict] = None
    doc_attachment_id: Optional[str] = None
    status: Optional[str] = None
