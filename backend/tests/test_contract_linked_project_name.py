# -*- coding: utf-8 -*-
"""关联商机名称 linked_project_name 不被 registration_json.project_name 字段策略误删。"""
import pytest

from app.domains.lowcode.field_permission import strip_entity_dicts


@pytest.mark.asyncio
async def test_strip_keeps_linked_project_name_when_reg_project_name_hidden(monkeypatch):
    """json_storage=registration_json 的 project_name 隐藏时，勿删顶层 linked_project_name。"""
    native_defs = [
        {
            "id": "project_name",
            "label": "项目名称",
            "json_storage": "registration_json",
            "visible_roles": ["admin"],
        },
        {
            "id": "project_id",
            "label": "关联商机",
            "companions": ["linked_project_name", "project_code"],
        },
    ]

    async def fake_schema(_db, _tenant_id, _entity_type):
        return {"native_fields": native_defs, "field_definitions": [], "rule_definitions": []}

    async def fake_custom(_db, _tenant_id, _entity_type):
        return []

    monkeypatch.setattr(
        "app.domains.lowcode.service.get_entity_form_schema",
        fake_schema,
    )
    monkeypatch.setattr(
        "app.domains.lowcode.service.get_entity_fields",
        fake_custom,
    )

    row = {
        "project_id": "proj-1",
        "linked_project_name": "山西潞安滚轴筛项目",
        "project_code": "PRJ001",
        "project_name": "山西潞安滚轴筛项目",
        "registration_json": {"project_name": "登记里的项目名称"},
    }
    await strip_entity_dicts(None, "t1", "contract", [row], ["salesperson"])
    assert row["linked_project_name"] == "山西潞安滚轴筛项目"
    assert row["project_id"] == "proj-1"
    assert row["registration_json"].get("project_name") is None
