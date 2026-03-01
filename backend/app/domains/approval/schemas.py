from pydantic import BaseModel
from typing import Optional


class ApprovalSubmit(BaseModel):
    biz_type: str  # quote_version / contract_version / change_request
    biz_id: str
    title: Optional[str] = None
    assignee_ids: list[str]  # 审批人 ID 列表 (按顺序)
    assignee_names: Optional[list[str]] = None


class ApprovalDecide(BaseModel):
    action: str  # approved / rejected
    comment: Optional[str] = None

    def model_post_init(self, __context) -> None:
        if self.action not in ("approved", "rejected"):
            raise ValueError("action 必须为 approved 或 rejected")
