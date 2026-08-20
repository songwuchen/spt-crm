# -*- coding: utf-8 -*-
"""客户服务申请：有区域经理时先审区域再进业务经理（串行绕行）。"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import (
    apply_cs_service_request_start_region_first,
    _flow_cs_service_start_not_region_first,
)


def _graph():
    nodes = [
        {"id": "start", "type": "start", "name": "流程发起节点"},
        {"id": "n1", "type": "approval", "name": "业务经理"},
        {"id": "n22", "type": "approval", "name": "区域经理或组长"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    # 故意把业务经理排在区域前面（旧生成器顺序）
    routes = [
        {
            "id": "r0", "source": "start", "target": "n1",
            "exclusive_group": "ex_start",
            "condition": {"field": "field_3", "operator": "eq", "value": "否"},
        },
        {
            "id": "r4", "source": "start", "target": "n22",
            "exclusive_group": "ex_start",
            "condition": {"field": "field_2", "operator": "is_not_empty"},
        },
        {
            "id": "r_back", "source": "n22", "target": "n1",
            "condition": {"field": "__always", "operator": "is_empty"},
        },
    ]
    return nodes, routes


def test_apply_region_first_order_and_exclusive():
    nodes, routes = _graph()
    assert _flow_cs_service_start_not_region_first(nodes, routes)
    assert apply_cs_service_request_start_region_first(nodes, routes)
    assert not _flow_cs_service_start_not_region_first(nodes, routes)
    start_outs = [r for r in routes if r["source"] == "start"]
    assert all(r.get("exclusive_group") == "ex_start" for r in start_outs)
    assert all(r.get("fork") != "parallel" for r in start_outs)
    assert start_outs[0]["target"] == "n22"


def test_field2_set_only_region_then_biz_via_chain():
    nodes, routes = _graph()
    apply_cs_service_request_start_region_first(nodes, routes)
    version = type("V", (), {"node_definitions": nodes, "route_definitions": routes})()
    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    fd = {"field_2": "u-region", "field_3": "否"}
    names = {
        next(n["name"] for n in nodes if n["id"] == t)
        for t in eng._next_targets(version, "start", fd)
    }
    assert names == {"区域经理或组长"}
    # 区域审完再进业务经理
    names2 = {
        next(n["name"] for n in nodes if n["id"] == t)
        for t in eng._next_targets(version, "n22", fd)
    }
    assert names2 == {"业务经理"}


def test_field2_empty_goes_biz_direct():
    nodes, routes = _graph()
    apply_cs_service_request_start_region_first(nodes, routes)
    version = type("V", (), {"node_definitions": nodes, "route_definitions": routes})()
    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    names = {
        next(n["name"] for n in nodes if n["id"] == t)
        for t in eng._next_targets(version, "start", {"field_3": "否"})
    }
    assert names == {"业务经理"}


def test_undoes_mistaken_parallel_fork():
    nodes, routes = _graph()
    for r in routes:
        if r["source"] == "start":
            r.pop("exclusive_group", None)
            r["fork"] = "parallel"
    assert _flow_cs_service_start_not_region_first(nodes, routes)
    assert apply_cs_service_request_start_region_first(nodes, routes)
    assert not _flow_cs_service_start_not_region_first(nodes, routes)
    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    version = type("V", (), {"node_definitions": nodes, "route_definitions": routes})()
    names = {
        next(n["name"] for n in nodes if n["id"] == t)
        for t in eng._next_targets(
            version, "start", {"field_2": "u1", "field_3": "否"},
        )
    }
    assert names == {"区域经理或组长"}


def test_product_replace_region_before_else_biz():
    from app.domains.lowcode.workflow_service import (
        apply_cs_product_replace_start_region_first,
        _flow_cs_product_replace_start_not_region_first,
    )

    nodes = [
        {"id": "start", "type": "start", "name": "流程发起节点"},
        {"id": "n1", "type": "approval", "name": "业务经理审批"},
        {"id": "n24", "type": "approval", "name": "区域经理或组长"},
        {"id": "n9", "type": "approval", "name": "客服补登"},
    ]
    routes = [
        {
            "source": "start", "target": "n9", "exclusive_group": "ex_start",
            "condition": {"field": "field_22", "operator": "eq", "value": "是"},
        },
        {
            "source": "start", "target": "n1", "exclusive_group": "ex_start",
            "condition": None,
        },
        {
            "source": "start", "target": "n24", "exclusive_group": "ex_start",
            "condition": {"field": "field_2", "operator": "is_not_empty"},
        },
        {
            "source": "n24", "target": "n1",
            "condition": {"field": "__always", "operator": "is_empty"},
        },
    ]
    assert _flow_cs_product_replace_start_not_region_first(nodes, routes)
    assert apply_cs_product_replace_start_region_first(nodes, routes)
    assert not _flow_cs_product_replace_start_not_region_first(nodes, routes)

    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    version = type("V", (), {"node_definitions": nodes, "route_definitions": routes})()
    names = {
        next(n["name"] for n in nodes if n["id"] == t)
        for t in eng._next_targets(version, "start", {"field_2": "u1", "field_22": "否"})
    }
    assert names == {"区域经理或组长"}
