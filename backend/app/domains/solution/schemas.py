from typing import Any, Optional, Union
from pydantic import BaseModel


class SolutionCreate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    config_json: Optional[Union[dict, list]] = None
    risk_list_json: Optional[Union[dict, list]] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    custom_fields_json: Optional[dict[str, Any]] = None


class SolutionUpdate(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    custom_fields_json: Optional[dict[str, Any]] = None


class SolutionVersionUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    config_json: Optional[Union[dict, list]] = None
    risk_list_json: Optional[Union[dict, list]] = None
    doc_attachment_id: Optional[str] = None
    status: Optional[str] = None
