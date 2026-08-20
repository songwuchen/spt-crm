# -*- coding: utf-8 -*-
"""客户服务申请：发起节点区域经理与业务经理可并行。"""
from __future__ import annotations

from app.domains.lowcode.workflow_service import (
    apply_cs_service_request_start_parallel,
    _flow_cs_service_start_not_parallel,
)


def _graph():
    nodes = [
        {"id": "start", "type": "start", "name": "流程发起节点"},
        {"id": "n1", "type": "approval", "name": "业务经理"},
        {"id": "n22", "type": "approval", "name": "区域经理或组长"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
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


def test_apply_ungroups_start_outs():
    nodes, routes = _graph()
    assert _flow_cs_service_start_not_parallel(nodes, routes)
    assert apply_cs_service_request_start_parallel(nodes, routes)
    assert not _flow_cs_service_start_not_parallel(nodes, routes)
    start_outs = [r for r in routes if r["source"] == "start"]
    assert all(r.get("fork") == "parallel" for r in start_outs)
    assert all(not r.get("exclusive_group") for r in start_outs)
    back = next(r for r in routes if r["source"] == "n22")
    assert back.get("reenter") is True


def test_both_region_and_biz_hit_when_field2_set():
    from unittest.mock import MagicMock

    from app.domains.lowcode.workflow_engine import WorkflowEngine, evaluate_condition

    nodes, routes = _graph()
    apply_cs_service_request_start_parallel(nodes, routes)
    version = type("V", (), {"node_definitions": nodes, "route_definitions": routes})()
    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    fd = {"field_2": "u-region", "field_3": "否"}
    targets = eng._next_targets(version, "start", fd)
    names = {next(n["name"] for n in nodes if n["id"] == t) for t in targets}
    assert names == {"业务经理", "区域经理或组长"}
    assert evaluate_condition(routes[0]["condition"], fd)
    assert evaluate_condition(routes[1]["condition"], fd)


def test_product_replace_start_ungroups_and_hits_region():
    from unittest.mock import MagicMock

    from app.domains.lowcode.workflow_engine import WorkflowEngine
    from app.domains.lowcode.workflow_service import (
        apply_cs_product_replace_start_parallel,
        _flow_cs_product_replace_start_not_parallel,
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
            "source": "start", "target": "n24", "exclusive_group": "ex_start",
            "condition": {"field": "field_2", "operator": "is_not_empty"},
        },
        {
            "source": "start", "target": "n1", "exclusive_group": "ex_start",
            "condition": None,
        },
        {
            "source": "n24", "target": "n1",
            "condition": {"field": "__always", "operator": "is_empty"},
        },
    ]
    assert _flow_cs_product_replace_start_not_parallel(nodes, routes)
    assert apply_cs_product_replace_start_parallel(nodes, routes)
    assert not _flow_cs_product_replace_start_not_parallel(nodes, routes)

    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    version = type("V", (), {"node_definitions": nodes, "route_definitions": routes})()
    # 有区域经理：应命中区域经理，不应走 else 业务经理
    names = {
        next(n["name"] for n in nodes if n["id"] == t)
        for t in eng._next_targets(version, "start", {"field_2": "u1", "field_22": "否"})
    }
    assert names == {"区域经理或组长"}
    back = next(r for r in routes if r["source"] == "n24")
    assert back.get("reenter") is True
    # 区域经理 + 客服补登可同时命中
    names2 = {
        next(n["name"] for n in nodes if n["id"] == t)
        for t in eng._next_targets(version, "start", {"field_2": "u1", "field_22": "是"})
    }
    assert names2 == {"区域经理或组长", "客服补登"}

