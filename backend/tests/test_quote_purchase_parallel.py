# -*- coding: utf-8 -*-
"""报价「是否转采购」须与部门通知并行，不能进财务核价互斥组。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import (
    apply_quote_purchase_inquiry_parallel,
    _flow_missing_exclusive_groups,
    _flow_quote_purchase_not_parallel,
    _form_need_purchase_yes,
    _serial_exclusive_outs,
)


def _quote_n2_graph(*, purchase_in_exclusive: bool = True):
    nodes = [
        {"id": "n2", "type": "approval", "name": "财务核价"},
        {"id": "n7", "type": "approval", "name": "通知发起人"},
        {"id": "n8", "type": "cc", "name": "抄送发起人"},
        {"id": "n15", "type": "approval", "name": "采购"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    r_purchase = {
        "id": "r_24", "source": "n2", "target": "n15",
        "condition": {"field": "need_purchase", "operator": "eq", "value": "是"},
    }
    if purchase_in_exclusive:
        r_purchase["exclusive_group"] = "ex_n2"
    else:
        r_purchase["fork"] = "parallel"
    routes = [
        {
            "id": "r_16", "source": "n2", "target": "n7",
            "exclusive_group": "ex_n2",
            "condition": {
                "field": "department", "operator": "in",
                "value": ["dept-metallurgy"],
            },
        },
        r_purchase,
        {"id": "r_18", "source": "n2", "target": "n8", "always": True},
        {"id": "r_14", "source": "n15", "target": "n2"},
    ]
    return nodes, routes


def test_apply_quote_purchase_inquiry_parallel_ungroups():
    nodes, routes = _quote_n2_graph(purchase_in_exclusive=True)
    assert _flow_quote_purchase_not_parallel(nodes, routes)
    assert apply_quote_purchase_inquiry_parallel(nodes, routes)
    purchase = next(r for r in routes if r["target"] == "n15")
    assert purchase.get("fork") == "parallel"
    assert not purchase.get("exclusive_group")
    back = next(r for r in routes if r["source"] == "n15")
    assert back.get("reenter") is True
    assert not _flow_quote_purchase_not_parallel(nodes, routes)
    assert not apply_quote_purchase_inquiry_parallel(nodes, routes)


def test_next_targets_purchase_parallel_with_dept():
    """冶金部门命中通知发起人时，转采购=是仍须同时进采购。"""
    nodes, routes = _quote_n2_graph(purchase_in_exclusive=True)
    apply_quote_purchase_inquiry_parallel(nodes, routes)
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    t = eng._next_targets(version, "n2", {
        "department": "dept-metallurgy",
        "need_purchase": "是",
    })
    assert "n15" in t
    assert "n7" in t
    assert "n8" in t


def test_next_targets_purchase_swallowed_by_exclusive_group():
    """修复前：互斥组先命中部门边，采购边永远走不到。"""
    nodes, routes = _quote_n2_graph(purchase_in_exclusive=True)
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    t = eng._next_targets(version, "n2", {
        "department": "dept-metallurgy",
        "need_purchase": "是",
    })
    assert "n7" in t
    assert "n15" not in t


def test_missing_exclusive_groups_ignores_parallel_purchase():
    nodes, routes = _quote_n2_graph(purchase_in_exclusive=True)
    apply_quote_purchase_inquiry_parallel(nodes, routes)
    assert _flow_missing_exclusive_groups(routes) is False
    serial = _serial_exclusive_outs([
        r for r in routes if r.get("source") == "n2" and not r.get("always")
    ])
    assert all(r.get("exclusive_group") for r in serial)
    assert any(r.get("fork") == "parallel" for r in routes)


def test_form_need_purchase_yes():
    assert _form_need_purchase_yes({"need_purchase": "是"})
    assert _form_need_purchase_yes({"need_purchase": ["是"]})
    assert not _form_need_purchase_yes({"need_purchase": "否"})
    assert not _form_need_purchase_yes({})


@pytest.mark.asyncio
async def test_advance_passes_reenter_to_finance():
    eng = WorkflowEngine(db=None, tenant_id="t")
    eng._activate_node = AsyncMock()
    version = SimpleNamespace(
        node_definitions=[
            {"id": "n2", "type": "approval", "name": "财务核价"},
            {"id": "end", "type": "end", "name": "结束"},
        ],
        route_definitions=[
            {"id": "r_14", "source": "n15", "target": "n2", "reenter": True},
        ],
    )
    inst = SimpleNamespace(status="running")
    await eng._advance(inst, version, "n15", SimpleNamespace(form_data={}))
    assert eng._activate_node.await_count == 1
    assert eng._activate_node.await_args.kwargs.get("allow_reenter") is True
