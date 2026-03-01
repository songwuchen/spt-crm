from pydantic import BaseModel
from typing import Optional


class ActivityCreate(BaseModel):
    biz_type: str
    biz_id: str
    activity_type: str
    subject: Optional[str] = None
    content: Optional[str] = None
    contact_name: Optional[str] = None
    result_json: Optional[dict] = None


class ActivityUpdate(BaseModel):
    subject: Optional[str] = None
    content: Optional[str] = None
    contact_name: Optional[str] = None
    result_json: Optional[dict] = None
