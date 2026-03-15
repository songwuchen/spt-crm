from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    customer_code: Optional[str] = Field(None, max_length=64)
    short_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = None
    scale_level: Optional[str] = None
    region: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = None
    level: Optional[str] = None
    owner_id: Optional[str] = None
    tags_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("A", "B", "C", "D"):
            raise ValueError("客户级别必须为 A/B/C/D")
        return v


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    customer_code: Optional[str] = Field(None, max_length=64)
    short_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = None
    scale_level: Optional[str] = None
    region: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    source: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[str] = None
    tags_json: Optional[dict] = None
    remark: Optional[str] = Field(None, max_length=2000)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("A", "B", "C", "D"):
            raise ValueError("客户级别必须为 A/B/C/D")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("active", "inactive"):
            raise ValueError("状态必须为 active/inactive")
        return v


class CustomerOut(BaseModel):
    id: str
    customer_code: Optional[str] = None
    name: str
    short_name: Optional[str] = None
    industry: Optional[str] = None
    scale_level: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    source: Optional[str] = None
    level: Optional[str] = None
    status: str
    tags_json: Optional[dict] = None
    remark: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    name: str
    title: Optional[str] = None
    role_type: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False
    reports_to_id: Optional[str] = None
    remark: Optional[str] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    role_type: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_primary: Optional[bool] = None
    reports_to_id: Optional[str] = None
    remark: Optional[str] = None


class ContactOut(BaseModel):
    id: str
    customer_id: str
    name: str
    title: Optional[str] = None
    role_type: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool
    reports_to_id: Optional[str] = None
    remark: Optional[str] = None

    model_config = {"from_attributes": True}


class RelationCreate(BaseModel):
    to_customer_id: str
    relation_type: str
    note: Optional[str] = None


class ShareCreate(BaseModel):
    shared_to_type: str = "user"
    shared_to_id: str
    shared_to_name: Optional[str] = None
    permission: str = "view"


class BatchReleaseRequest(BaseModel):
    customer_ids: List[str]
