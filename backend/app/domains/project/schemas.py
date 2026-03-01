from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    customer_id: Optional[str] = None
    stage_code: Optional[str] = "S1"
    amount_expect: Optional[float] = Field(None, ge=0)
    probability: Optional[int] = Field(None, ge=0, le=100)
    close_date_expect: Optional[str] = None
    competitors_json: Optional[dict] = None
    key_requirements_json: Optional[dict] = None
    risk_level: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=2000)

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
    close_date_expect: Optional[str] = None
    competitors_json: Optional[dict] = None
    key_requirements_json: Optional[dict] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None
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


class StageAdvance(BaseModel):
    to_stage: str
    note: Optional[str] = None
    force: Optional[bool] = False


class StageRollback(BaseModel):
    to_stage: str
    note: Optional[str] = None
