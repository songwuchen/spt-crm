# -*- coding: utf-8 -*-
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_models import WfProcessDefinitionVersion
from app.domains.lowcode.workflow_service import (
    _XUNHAN_FEEDBACK_REENTER_EDGES,
    _drawing_flow_graph,
    patch_xunhan_contract_review_feedback_routes,
)


def test_xunhan_feedback_routes_have_reenter():
    nodes, routes = _drawing_flow_graph("xunhan_contract_review")
    assert patch_xunhan_contract_review_feedback_routes(routes) is False
    got = {
        (r.get("source"), r.get("target"))
        for r in routes
        if r.get("reenter")
    }
    assert got >= set(_XUNHAN_FEEDBACK_REENTER_EDGES)


def test_xunhan_design1_can_reenter_gm_after_feedback():
    """设计审批1 完成后须能再次激活总经理（反馈第二轮）。"""
    nodes, routes = _drawing_flow_graph("xunhan_contract_review")
    ver = WfProcessDefinitionVersion()
    ver.node_definitions = nodes
    ver.route_definitions = routes
    eng = WorkflowEngine(None, "t")
    fd = {"need_feedback": "是"}
    outs = eng._outgoing(ver, "n28__1")
    gm = next(r for r in outs if r.get("target") == "n5")
    assert gm.get("reenter") is True
    assert "n5" in eng._next_targets(ver, "n28__1", fd)
