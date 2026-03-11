from typing import Optional, List
from pydantic import BaseModel


class NotificationCreate(BaseModel):
    recipient_id: str
    type: str
    title: str
    content: Optional[str] = None
    biz_type: Optional[str] = None
    biz_id: Optional[str] = None
    sender_name: Optional[str] = None
    extra_json: Optional[dict] = None


class MarkReadRequest(BaseModel):
    ids: List[str]


class UpdatePreferencesRequest(BaseModel):
    preferences: dict[str, bool] = {}  # e.g. {"approval_pending": true, "stage_change": false}
