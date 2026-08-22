# -*- coding: utf-8 -*-
"""合同评审反馈回路：再入总经理/财务须标 reenter。"""
from __future__ import annotations

from app.domains.lowcode.workflow_service import (
    _contract_review_feedback_reenter_aligned,
    _contract_review_flow_graph,
    apply_contract_review_feedback_reenter,
)


def test_contract_review_feedback_routes_mark_reenter():
    _nodes, routes = _contract_review_flow_graph()
    assert _contract_review_feedback_reenter_aligned(routes)
    by_id = {r["id"]: r for r in routes if isinstance(r, dict) and r.get("id")}
    assert by_id["r_design_fb_gm"].get("reenter") is True
    assert by_id["r_fb_biz_gm"].get("reenter") is True
    assert by_id["r_gm_fin"].get("reenter") is True


def test_apply_contract_review_feedback_reenter_patches_old_routes():
    routes = [
        {"id": "r_design_fb_gm", "source": "approval_design_fb", "target": "approval_gm"},
        {"id": "r_fb_biz_gm", "source": "approval_feedback_biz", "target": "approval_gm"},
        {"id": "r_gm_fin", "source": "approval_gm", "target": "approval_finance_opinion"},
        {"id": "r_other", "source": "approval_biz", "target": "approval_legal"},
    ]
    assert not _contract_review_feedback_reenter_aligned(routes)
    assert apply_contract_review_feedback_reenter(routes) is True
    assert _contract_review_feedback_reenter_aligned(routes)
    assert apply_contract_review_feedback_reenter(routes) is False
