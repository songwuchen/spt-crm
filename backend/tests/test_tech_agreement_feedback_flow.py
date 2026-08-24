# -*- coding: utf-8 -*-
from app.domains.lowcode.workflow_service import (
    _TECH_FB_CC_APPLICANT,
    _TECH_FB_CC_SALES,
    _flow_is_jdy_tech_agreement_feedback,
    _flow_missing_tech_agreement_feedback_flow,
    apply_tech_agreement_feedback_flow,
    build_tech_agreement_feedback_flow,
)


def _legacy_flow():
    nodes = [
        {"id": "start", "type": "start", "name": "发起"},
        {"id": "n_design_review", "type": "approval", "name": "设计审核",
         "approver_rule": {"type": "form_field_person", "value": "design_reviewer"}},
        {"id": "n_dept_clerk", "type": "approval", "name": "部门内勤",
         "approver_rule": {"type": "form_field_person", "value": "dept_clerk"}},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes = [
        {"id": "r1", "source": "start", "target": "n_design_review"},
        {"id": "r2", "source": "n_design_review", "target": "n_dept_clerk"},
        {"id": "r3", "source": "n_dept_clerk", "target": "end"},
    ]
    return nodes, routes


def test_build_tech_agreement_feedback_flow_topology():
    nodes, routes = build_tech_agreement_feedback_flow()
    names = {n["name"] for n in nodes}
    assert "总工意见" in names
    assert "内勤核查" in names
    assert "财务核算" in names
    assert "总经理审批" in names
    assert "通知1" in names
    assert _flow_is_jdy_tech_agreement_feedback(nodes, routes)
    assert any(
        r.get("source") == "n_clerk_verify" and r.get("exclusive_group") == "ex_sales"
        for r in routes
    )
    assert any(
        r.get("source") == "start" and r.get("target") == _TECH_FB_CC_SALES and r.get("always")
        for r in routes
    )


def test_apply_tech_agreement_feedback_flow_replaces_legacy():
    nodes, routes = _legacy_flow()
    assert _flow_missing_tech_agreement_feedback_flow(nodes, routes) is True
    assert apply_tech_agreement_feedback_flow(nodes, routes) is True
    assert _flow_missing_tech_agreement_feedback_flow(nodes, routes) is False
    assert apply_tech_agreement_feedback_flow(nodes, routes) is False
    assert _flow_is_jdy_tech_agreement_feedback(nodes, routes) is True
    cc_sales = next(n for n in nodes if n["id"] == _TECH_FB_CC_SALES)
    assert cc_sales["approver_rule"]["value"] == "salesperson"
    cc_app = next(n for n in nodes if n["id"] == _TECH_FB_CC_APPLICANT)
    assert cc_app["approver_rule"]["type"] == "mixed"
    assert not any(
        r.get("source") in (_TECH_FB_CC_SALES, _TECH_FB_CC_APPLICANT) and r.get("target") == "end"
        for r in routes
    )
