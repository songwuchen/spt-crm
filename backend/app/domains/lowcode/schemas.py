"""扩展平台 — 表单引擎 Pydantic schemas。

移植自 spt-lowcode app/schemas/form/template.py,id 统一为 str(String(36))。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ===== 字段 / 规则定义(前端设计器产出的 JSON) =====

class FieldDefinition(BaseModel):
    id: str
    type: str
    label: str
    placeholder: str | None = None
    description: str | None = None
    required: bool = False
    default_value: Any = None
    options: list[dict[str, Any]] | None = None
    props: dict[str, Any] = Field(default_factory=dict)
    detail_table_columns: list["FieldDefinition"] | None = None
    is_indexed: bool = False
    span: int | None = None
    # 字段级权限(按角色 code)。空/缺省 = 不限制(所有人)。
    # visible_roles: 谁能看到该字段; edit_roles: 谁能编辑(可见但不可编辑 → 只读)。
    visible_roles: list[str] | None = None
    edit_roles: list[str] | None = None


class FormRuleDefinition(BaseModel):
    id: str
    type: str  # visibility / validation / formula / readonly
    target_field_id: str = ""
    target_field_ids: list[str] = Field(default_factory=list)
    condition: dict[str, Any] = Field(default_factory=dict)
    action: dict[str, Any] = Field(default_factory=dict)


# ===== 模板 CRUD =====

class FormTemplateCreate(BaseModel):
    name: str = Field(max_length=128)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    sort_order: int = 0


class FormTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    sort_order: int | None = None


class FormTemplateOut(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    status: str
    current_version: int
    sort_order: int
    is_system: bool = False
    entity_type: str | None = None

    model_config = {"from_attributes": True}


class SaveDesignRequest(BaseModel):
    """保存表单设计(字段/布局/规则),写入 draft 版本。"""
    field_definitions: list[FieldDefinition]
    layout_definition: dict[str, Any] = Field(default_factory=dict)
    rule_definitions: list[FormRuleDefinition] = Field(default_factory=list)


class FormTemplateVersionOut(BaseModel):
    id: str
    template_id: str
    version_number: int
    field_definitions: list[dict[str, Any]]
    layout_definition: dict[str, Any]
    rule_definitions: list[dict[str, Any]]
    status: str
    published_at: datetime | None = None
    published_by: str | None = None

    model_config = {"from_attributes": True}


# ===== 表单实例(填报/提交) =====

class FormInstanceCreate(BaseModel):
    template_id: str
    form_data: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    remark: str | None = None
    # 是否仅暂存草稿(不触发流程/校验必填)。
    as_draft: bool = False


class FormInstanceUpdate(BaseModel):
    form_data: dict[str, Any] | None = None
    title: str | None = None
    remark: str | None = None


class FormInstanceOut(BaseModel):
    id: str
    template_id: str
    template_version_id: str
    business_no: str | None = None
    title: str | None = None
    status: str
    initiator_id: str
    initiator_dept_id: str | None = None
    amount: Decimal | None = None
    form_data: dict[str, Any]
    field_definitions: list[dict[str, Any]]
    remark: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FormInstanceListItem(BaseModel):
    """列表行(不含完整 field_definitions 快照,减小载荷)。"""
    id: str
    template_id: str
    business_no: str | None = None
    title: str | None = None
    status: str
    initiator_id: str
    amount: Decimal | None = None
    form_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
