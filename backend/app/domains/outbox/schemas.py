from typing import Optional
from pydantic import BaseModel, Field


class OutboxEventCreate(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    aggregate_type: str = Field(..., min_length=1, max_length=64)
    aggregate_id: str = Field(..., min_length=1, max_length=36)
    payload_json: Optional[dict] = None


class InboxEventCreate(BaseModel):
    source: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., min_length=1, max_length=100)
    external_id: Optional[str] = Field(None, max_length=200)
    payload_json: Optional[dict] = None
