from pydantic import BaseModel
from typing import Optional
from datetime import date


class ActivityCreate(BaseModel):
    biz_type: str
    biz_id: str
    activity_type: str
    subject: Optional[str] = None
    content: Optional[str] = None
    contact_id: Optional[str] = None
    contact_name: Optional[str] = None
    result_json: Optional[dict] = None
    next_follow_date: Optional[date] = None
    biz_name: Optional[str] = None


class ActivityUpdate(BaseModel):
    subject: Optional[str] = None
    content: Optional[str] = None
    contact_id: Optional[str] = None
    contact_name: Optional[str] = None
    result_json: Optional[dict] = None
    next_follow_date: Optional[date] = None
