"""扩展平台 — 审批流程引擎 Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WfDefinitionCreate(BaseModel):
    name: str = Field(max_length=128)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    form_template_id: str | None = None   # 绑定的自定义表单
    biz_type: str | None = None           # 或绑定既有业务类型(替换旧引擎)


class WfDefinitionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    form_template_id: str | None = None
    biz_type: str | None = None


class WfDefinitionOut(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    status: str
    current_version: int
    form_template_id: str | None = None
    biz_type: str | None = None

    model_config = {"from_attributes": True}


class WfSaveDesign(BaseModel):
    """保存流程设计(节点/连线/审批人规则),写入 draft 版本。"""
    node_definitions: list[dict[str, Any]] = Field(default_factory=list)
    route_definitions: list[dict[str, Any]] = Field(default_factory=list)
    approver_rules: list[dict[str, Any]] = Field(default_factory=list)


class WfVersionOut(BaseModel):
    id: str
    process_definition_id: str
    version_number: int
    node_definitions: list[dict[str, Any]]
    route_definitions: list[dict[str, Any]]
    approver_rules: list[dict[str, Any]]
    status: str

    model_config = {"from_attributes": True}


class WfActRequest(BaseModel):
    action: str                     # approve / reject / transfer / comment
    opinion: str | None = None
    transfer_to: str | None = None  # transfer 时的接收人
