from typing import Optional, List, Union
from datetime import date
from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    customer_id: Optional[str] = None
    stage_code: Optional[str] = "S1"
    amount_expect: Optional[float] = Field(None, ge=0)
    probability: Optional[int] = Field(None, ge=0, le=100)
    close_date_expect: Optional[date] = None
    biz_date: Optional[date] = None
    competitors_json: Optional[dict] = None
    key_requirements_json: Optional[Union[dict, list]] = None  # 多条需求明细(数组)，兼容旧版单条 dict
    risk_level: Optional[str] = None
    has_guarantee: Optional[bool] = None
    has_weight_requirement: Optional[bool] = None
    uses_idle_equipment: Optional[bool] = None
    payment_method: Optional[str] = Field(None, max_length=64)
    custom_fields_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=2000)
    # 创建时可指定负责人（默认取录入人）；主要供批量导入按姓名指派负责人使用
    owner_id: Optional[str] = Field(None, max_length=36)

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("L", "M", "H"):
            raise ValueError("风险等级必须为 L/M/H")
        return v


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    customer_id: Optional[str] = None
    amount_expect: Optional[float] = Field(None, ge=0)
    probability: Optional[int] = Field(None, ge=0, le=100)
    close_date_expect: Optional[date] = None
    biz_date: Optional[date] = None
    competitors_json: Optional[dict] = None
    key_requirements_json: Optional[Union[dict, list]] = None  # 多条需求明细(数组)，兼容旧版单条 dict
    risk_level: Optional[str] = None
    has_guarantee: Optional[bool] = None
    has_weight_requirement: Optional[bool] = None
    uses_idle_equipment: Optional[bool] = None
    payment_method: Optional[str] = Field(None, max_length=64)
    status: Optional[str] = None
    custom_fields_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("L", "M", "H"):
            raise ValueError("风险等级必须为 L/M/H")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("active", "won", "lost", "suspended"):
            raise ValueError("状态必须为 active/won/lost/suspended")
        return v


class ProjectTransfer(BaseModel):
    """转移商机负责人。受 project:transfer 权限单独保护，与普通编辑(project:edit)分离。"""
    owner_id: str = Field(..., min_length=1, max_length=36)
    note: Optional[str] = Field(None, max_length=500)


class ProjectMemberAdd(BaseModel):
    user_id: str = Field(..., min_length=1)
    user_name: Optional[str] = None
    member_role: Optional[str] = Field(None, max_length=32)  # presale/business/delivery/finance/pm
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    permission: Optional[str] = "view"

    @field_validator("permission")
    @classmethod
    def validate_permission(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("view", "edit"):
            raise ValueError("权限必须为 view/edit")
        return v


class ProjectMemberUpdate(BaseModel):
    member_role: Optional[str] = Field(None, max_length=32)
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    permission: Optional[str] = None

    @field_validator("permission")
    @classmethod
    def validate_permission(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("view", "edit"):
            raise ValueError("权限必须为 view/edit")
        return v


class StageAdvance(BaseModel):
    to_stage: str
    note: Optional[str] = None
    force: Optional[bool] = False


class StageRollback(BaseModel):
    to_stage: str
    note: Optional[str] = None
