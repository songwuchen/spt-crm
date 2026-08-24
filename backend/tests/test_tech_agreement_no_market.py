# -*- coding: utf-8 -*-
"""技术协议评审默认拓扑：无市场支持中心。"""
from app.domains.lowcode.workflow_service import (
    _flow_is_tech_agreement_jdy,
    _tech_agreement_flow_graph,
)


def test_tech_agreement_flow_drops_market_support():
    nodes, routes = _tech_agreement_flow_graph()
    names = {n.get("name") for n in nodes}
    ids = {n.get("id") for n in nodes}
    assert "市场支持中心" not in names
    assert "approval_market" not in ids
    assert "部门审批" in names and "总工审批" in names
    assert any(
        r.get("source") == "approval_dept" and r.get("target") == "approval_chief"
        for r in routes
    )
    assert not any(r.get("target") == "approval_market" for r in routes)
    assert _flow_is_tech_agreement_jdy(nodes)


def test_tech_agreement_flow_with_market_needs_upgrade():
    nodes, _ = _tech_agreement_flow_graph()
    # 人为加回市场支持中心 → 视为未对齐
    nodes = list(nodes) + [
        {"id": "approval_market", "type": "approval", "name": "市场支持中心"},
    ]
    assert not _flow_is_tech_agreement_jdy(nodes)
