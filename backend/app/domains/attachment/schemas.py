from typing import Optional
from pydantic import BaseModel


class AttachmentOut(BaseModel):
    id: str
    original_name: str
    content_type: Optional[str] = None
    file_size: int
    uploader_id: str
    uploader_name: Optional[str] = None
    created_at: str = ""

    model_config = {"from_attributes": True}
