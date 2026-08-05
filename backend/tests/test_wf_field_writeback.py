"""审批节点 field_perms 校验与默认流挂载。"""
from __future__ import annotations

import pytest

from app.common.exceptions import BusinessException
from app.domains.lowcode.wf_field_writeback import parse_field_perms, validate_field_updates
from app.domains.lowcode.workflow_service import (
    _contract_review_flow_graph,
    _contract_version_flow_graph,
)


def test_parse_field_perms_normalizes():
    node = {
        "field_perms": [
            {"field": "legal_risk", "access": "required"},
            {"id": "clause_opinion", "access": "edit"},  # 非法 access → editable
            {"access": "required"},  # 无 field → 跳过
        ]
    }
    perms = parse_field_perms(node)
    assert perms == [
        {"field": "legal_risk", "access": "required"},
        {"field": "clause_opinion", "access": "editable"},
    ]


def test_validate_rejects_unknown_and_missing_required():
    perms = [
        {"field": "legal_risk", "access": "required"},
        {"field": "legal_risk_desc", "access": "editable"},
    ]
    with pytest.raises(BusinessException) as ei:
        validate_field_updates(perms, {"hack": 1}, action="approve")
    assert "不可填写" in ei.value.message

    with pytest.raises(BusinessException) as ei2:
        validate_field_updates(perms, {"legal_risk_desc": "x"}, action="approve")
    assert "必填" in ei2.value.message

    ok = validate_field_updates(
        perms, {"legal_risk": "高", "legal_risk_desc": "ok"}, action="approve",
    )
    assert ok["legal_risk"] == "高"


def test_validate_opinion_required():
    with pytest.raises(BusinessException):
        validate_field_updates([], {}, opinion="", opinion_required=True, action="approve")
    assert validate_field_updates([], {}, opinion="同意", opinion_required=True, action="approve") == {}


def test_contract_review_default_has_field_perms():
    nodes, routes = _contract_review_flow_graph()
    by_id = {n["id"]: n for n in nodes}
    assert by_id["approval_legal"]["field_perms"]
    assert any(p["field"] == "legal_risk" and p["access"] == "required"
               for p in by_id["approval_legal"]["field_perms"])
    assert by_id["approval_gm"].get("opinion_required") is True
    assert any(p["field"] == "biz_risk" for p in by_id["approval_biz"]["field_perms"])
    assert "approval_legal_sup" in by_id
    assert "approval_region" in by_id
    assert "approval_info_feedback" in by_id
    assert "approval_design_fb" in by_id
    assert by_id["approval_initiator"]["approver_rule"]["type"] == "creator"
    # 旁路抄送
    for cid in ("cc_owner", "cc_install", "cc_related", "cc_lili", "cc_xunhan"):
        assert by_id[cid]["type"] == "cc"
    assert any(r.get("source") == "start" and r.get("target") == "cc_owner" and r.get("always")
               for r in routes)
    assert any(
        r.get("source") == "approval_design_fb" and r.get("target") == "approval_gm"
        for r in routes
    )
    assert any(
        r.get("source") == "approval_legal" and r.get("target") == "approval_legal_sup"
        for r in routes
    )
    # 出口：出口=是 且部门名不含「国际」
    export_r = next(
        r for r in routes
        if r.get("source") == "approval_biz" and r.get("target") == "approval_export"
    )
    fields = {c.get("field") for c in (export_r.get("condition") or {}).get("cond") or []}
    assert "is_export" in fields and "department_name" in fields
    # 产采质汇聚后直达结束（不再经抄送闸门）
    assert any(r.get("source") == "merge_ops_post" and r.get("target") == "end" for r in routes)


def test_contract_version_default_has_ops_field_perms():
    nodes, _ = _contract_version_flow_graph()
    by_id = {n["id"]: n for n in nodes}
    purch = by_id["approval_procurement"]["field_perms"]
    assert any(p["field"] == "purchasers" and p["access"] == "required" for p in purch)
    assert any(p["field"] == "inspectors" and p["access"] == "required"
               for p in by_id["approval_qc"]["field_perms"])
    assert any(p["field"] == "fill_code" for p in by_id["approval_warehouse"]["field_perms"])
    fin_fp = by_id["approval_finance"]["field_perms"]
    assert any(p["field"] == "contract_type" and p["access"] == "required" for p in fin_fp)
    assert any(p["field"] == "accept_method" and p["access"] == "required" for p in fin_fp)
    assert any(p["field"] == "accept_materials" and p["access"] == "editable" for p in fin_fp)
    assert any(p["field"] == "accept_date" and p["access"] == "editable" for p in fin_fp)


def test_next_targets_always_cc_does_not_steal_else():
    """旁路抄送 always 边不抢占区域经理/业务部门的 else 语义。"""
    from types import SimpleNamespace

    from app.domains.lowcode.workflow_engine import WorkflowEngine

    _, routes = _contract_review_flow_graph()
    version = SimpleNamespace(route_definitions=routes, node_definitions=[])
    eng = WorkflowEngine(db=None, tenant_id="t")

    # 有区域经理：应走区域经理 + 旁路抄送，不直接走业务部门
    t1 = eng._next_targets(version, "start", {
        "review_type": "合同评审",
        "region_manager_id": "u1",
        "need_install": "负责安装",
    })
    assert "approval_region" in t1
    assert "cc_owner" in t1
    assert "cc_install" in t1
    assert "approval_biz" not in t1

    # 无区域经理：else 走业务部门，同时旁路抄送
    t2 = eng._next_targets(version, "start", {
        "review_type": "合同评审",
        "need_install": "指导安装",
    })
    assert "approval_biz" in t2
    assert "cc_owner" in t2
    assert "cc_install" not in t2
    assert "approval_region" not in t2
