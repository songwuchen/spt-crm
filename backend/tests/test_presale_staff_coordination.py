# -*- coding: utf-8 -*-
"""售前服务通知：人员协调节点与总工审批字段联动回归。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.domains.lowcode.approver_resolver import ApprovalContext, ApproverResolver
from app.domains.lowcode.wf_field_writeback import validate_field_updates
from app.domains.lowcode.workflow_service import (
    apply_presale_chief_staff_coordination_required,
    _flow_presale_chief_needs_staff_coordination_required,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "presale_wmgf_856c322e.json"
WANG_ID = "1ba1708e-62ee-45af-8f52-483b5637ce0b"


def _chief_node(nodes: list[dict]) -> dict:
    return next(n for n in nodes if n.get("name") == "总工审批")


def _coord_node(nodes: list[dict]) -> dict:
    return next(n for n in nodes if n.get("name") == "人员协调")


def test_apply_presale_chief_staff_coordination_required():
    nodes = [{
        "id": "n2", "name": "总工审批", "type": "approval",
        "field_perms": [
            {"field": "staff_coordination", "access": "editable"},
            {"field": "need_xjwm_staff", "access": "required"},
        ],
    }]
    assert apply_presale_chief_staff_coordination_required(nodes)
    perms = {p["field"]: p["access"] for p in nodes[0]["field_perms"]}
    assert perms["staff_coordination"] == "required"
    assert not apply_presale_chief_staff_coordination_required(nodes)


def test_flow_needs_staff_coordination_patch():
    nodes = [_chief_node([{"name": "总工审批", "field_perms": [
        {"field": "staff_coordination", "access": "editable"},
    ]}])]
    assert _flow_presale_chief_needs_staff_coordination_required(nodes)


def test_chief_approve_without_staff_coordination_blocked_after_patch():
    nodes = [{
        "id": "n2", "name": "总工审批", "type": "approval",
        "field_perms": [
            {"field": "staff_coordination", "access": "editable"},
            {"field": "need_xjwm_staff", "access": "required"},
        ],
    }]
    apply_presale_chief_staff_coordination_required(nodes)
    perms = nodes[0]["field_perms"]
    from app.common.exceptions import BusinessException

    with pytest.raises(BusinessException):
        validate_field_updates(
            perms,
            {"need_xjwm_staff": "否"},
            action="approve",
            form_fields=[{"id": "staff_coordination", "label": "人员协调", "type": "person_multi"}],
        )


@pytest.mark.asyncio
async def test_coord_node_resolves_when_staff_filled(db):
    """form_data 有人员 UUID 时，人员协调应解析出审批人（非空审）。"""
    if not FIXTURE.exists():
        pytest.skip(f"missing fixture {FIXTURE}; run _export_presale_205_fixture.py")
    from sqlalchemy import select
    from app.domains.auth.models import User
    from tests.lead_intel_helpers import DEMO_TENANT

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    nodes = copy.deepcopy(data["node_definitions"])
    coord = _coord_node(nodes)
    assert coord["approver_rule"]["value"] == "staff_coordination"

    # 本地库可能没有 205 的王东明，用 fixture 里的 UUID 或任意在职用户验证解析逻辑
    uid = WANG_ID
    u = await db.get(User, uid)
    if u is None or not u.is_active:
        uid = (await db.execute(
            select(User.id).where(User.tenant_id == DEMO_TENANT, User.is_active == True).limit(1)  # noqa: E712
        )).scalar_one_or_none()
        if not uid:
            pytest.skip("no active user in local db")
    fd = {**data["form_data"], "staff_coordination": [uid]}

    resolver = ApproverResolver(db, DEMO_TENANT)
    ctx = ApprovalContext(initiator_id=data["initiator_id"], form_data=fd)
    uids = await resolver.resolve(coord["approver_rule"], ctx)
    assert uids == [uid]


@pytest.mark.asyncio
async def test_coord_node_empty_form_data_no_approver(db):
    if not FIXTURE.exists():
        pytest.skip(f"missing fixture {FIXTURE}")
    from tests.lead_intel_helpers import DEMO_TENANT

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    coord = _coord_node(data["node_definitions"])

    resolver = ApproverResolver(db, DEMO_TENANT)
    ctx = ApprovalContext(initiator_id=data["initiator_id"], form_data={})
    uids = await resolver.resolve(coord["approver_rule"], ctx)
    assert uids == []


def test_205_repro_timeline_documents_bug():
    """文档化 205 单 24.13-202608190001 根因：首次总工通过未写 staff_coordination。"""
    if not FIXTURE.exists():
        pytest.skip(f"missing fixture {FIXTURE}")
    logs = json.loads(FIXTURE.read_text(encoding="utf-8"))["action_logs"]
    actions = [lg["action"] for lg in logs]
    assert "auto_approve" in actions
    assert actions.index("approve") < actions.index("auto_approve")
