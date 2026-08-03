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
    nodes, _ = _contract_review_flow_graph()
    by_id = {n["id"]: n for n in nodes}
    assert by_id["approval_legal"]["field_perms"]
    assert any(p["field"] == "legal_risk" and p["access"] == "required"
               for p in by_id["approval_legal"]["field_perms"])
    assert by_id["approval_gm"].get("opinion_required") is True
    assert any(p["field"] == "biz_risk" for p in by_id["approval_biz"]["field_perms"])


def test_contract_version_default_has_ops_field_perms():
    nodes, _ = _contract_version_flow_graph()
    by_id = {n["id"]: n for n in nodes}
    purch = by_id["approval_procurement"]["field_perms"]
    assert any(p["field"] == "purchasers" and p["access"] == "required" for p in purch)
    assert any(p["field"] == "inspectors" and p["access"] == "required"
               for p in by_id["approval_qc"]["field_perms"])
    assert any(p["field"] == "fill_code" for p in by_id["approval_warehouse"]["field_perms"])
