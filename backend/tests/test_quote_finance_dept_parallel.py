# -*- coding: utf-8 -*-
"""报价财务核价后部门通知：多条件可同时命中；采购回路二次核价可重入。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import (
    apply_quote_finance_dept_notify_parallel,
    apply_quote_notify_initiator_after_no_purchase,
    apply_quote_purchase_inquiry_parallel,
    _flow_missing_exclusive_groups,
    _flow_quote_finance_dept_not_parallel,
    _flow_quote_notify_initiator_missing_purchase_gate,
)


XJ = "dept-xinjiang"
METAL = "dept-metallurgy"
MINE = "dept-mine"


def _quote_finance_graph(*, exclusive: bool = True):
    nodes = [
        {"id": "n2", "type": "approval", "name": "财务核价"},
        {"id": "n6", "type": "approval", "name": "通知销售经理"},
        {"id": "n7", "type": "approval", "name": "通知发起人"},
        {"id": "n8", "type": "cc", "name": "抄送发起人"},
        {"id": "n12", "type": "approval", "name": "热能"},
        {"id": "n14", "type": "approval", "name": "冶金装备销售事业部"},
        {"id": "n15", "type": "approval", "name": "采购"},
        {"id": "n16", "type": "approval", "name": "通知矿山工程装备销售"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes = [
        {
            "id": "r6", "source": "n2", "target": "n6",
            **({"exclusive_group": "ex_n2"} if exclusive else {}),
        },
        {
            "id": "r7", "source": "n2", "target": "n7",
            "condition": {
                "field": "department", "operator": "in",
                "value": [XJ, METAL, MINE],
            },
            **({"exclusive_group": "ex_n2"} if exclusive else {"fork": "parallel"}),
        },
        {"id": "r8", "source": "n2", "target": "n8", "always": True},
        {
            "id": "r12", "source": "n2", "target": "n12",
            "condition": {
                "field": "department", "operator": "in", "value": [XJ],
            },
            **({"exclusive_group": "ex_n2"} if exclusive else {"fork": "parallel"}),
        },
        {
            "id": "r14", "source": "n2", "target": "n14",
            "condition": {
                "field": "department", "operator": "in", "value": [METAL],
            },
            **({"exclusive_group": "ex_n2"} if exclusive else {"fork": "parallel"}),
        },
        {
            "id": "r15", "source": "n2", "target": "n15",
            "condition": {
                "field": "need_purchase", "operator": "eq", "value": "是",
            },
            **({"exclusive_group": "ex_n2"} if exclusive else {"fork": "parallel"}),
        },
        {
            "id": "r16", "source": "n2", "target": "n16",
            "condition": {
                "field": "department", "operator": "in", "value": [MINE],
            },
            **({"exclusive_group": "ex_n2"} if exclusive else {"fork": "parallel"}),
        },
        {"id": "r_back", "source": "n15", "target": "n2"},
    ]
    return nodes, routes


def _patch_all(nodes, routes):
    apply_quote_purchase_inquiry_parallel(nodes, routes)
    apply_quote_finance_dept_notify_parallel(nodes, routes)
    apply_quote_notify_initiator_after_no_purchase(nodes, routes)


def test_apply_ungroups_overlapping_dept_edges():
    nodes, routes = _quote_finance_graph(exclusive=True)
    assert _flow_quote_finance_dept_not_parallel(nodes, routes)
    assert apply_quote_finance_dept_notify_parallel(nodes, routes)
    apply_quote_purchase_inquiry_parallel(nodes, routes)
    assert not _flow_quote_finance_dept_not_parallel(nodes, routes)
    assert not apply_quote_finance_dept_notify_parallel(nodes, routes)
    assert _flow_missing_exclusive_groups(routes) is False
    assert all(
        r.get("reenter")
        for r in routes
        if r.get("source") == "n2"
        and r.get("target") in {"n6", "n7", "n12", "n14", "n16"}
    )


def test_xinjiang_hits_both_notify_initiator_and_thermal():
    """修复前互斥只走通知发起人，热能(段荣凯)永远不到。"""
    nodes, routes = _quote_finance_graph(exclusive=True)
    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    before = eng._next_targets(version, "n2", {"department": XJ, "need_purchase": "否"})
    assert "n7" in before
    assert "n12" not in before

    _patch_all(nodes, routes)
    after = eng._next_targets(version, "n2", {"department": XJ, "need_purchase": "否"})
    assert "n7" in after
    assert "n12" in after
    assert "n8" in after
    assert "n6" not in after


def test_else_sales_manager_when_no_dept_match():
    nodes, routes = _quote_finance_graph(exclusive=True)
    _patch_all(nodes, routes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    t = eng._next_targets(version, "n2", {
        "department": "dept-other", "need_purchase": "否",
    })
    assert "n6" in t
    assert "n7" not in t
    assert "n12" not in t
    assert "n8" in t


def test_mine_dept_purchase_yes_skips_initiator_keeps_mine():
    """简道云实单：第一次转采购=是 → 采购+矿山，不走通知发起人。"""
    nodes, routes = _quote_finance_graph(exclusive=True)
    assert _flow_quote_notify_initiator_missing_purchase_gate(nodes, routes)
    _patch_all(nodes, routes)
    assert not _flow_quote_notify_initiator_missing_purchase_gate(nodes, routes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    t = eng._next_targets(version, "n2", {
        "department": MINE, "need_purchase": "是",
    })
    assert "n15" in t
    assert "n16" in t
    assert "n7" not in t
    assert "n8" in t


def test_mine_dept_purchase_no_hits_initiator_and_mine():
    """第二次转采购=否 → 通知发起人+矿山并行。"""
    nodes, routes = _quote_finance_graph(exclusive=True)
    _patch_all(nodes, routes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    t = eng._next_targets(version, "n2", {
        "department": MINE, "need_purchase": "否",
    })
    assert "n7" in t
    assert "n16" in t
    assert "n15" not in t
    assert "n8" in t


@pytest.mark.asyncio
async def test_second_finance_reenters_dept_notify():
    """采购回财务后，部门通知边带 reenter，允许再次激活已完成节点。"""
    nodes, routes = _quote_finance_graph(exclusive=True)
    _patch_all(nodes, routes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    eng._activate_node = AsyncMock()
    version = SimpleNamespace(node_definitions=nodes, route_definitions=routes)
    # 模拟第二次财务核价推进（表单已改为否）
    inst = SimpleNamespace(status="running")
    # 直接测 advance 从 n2 出发时 reenter 标记
    reenter_targets = {
        r.get("target")
        for r in routes
        if r.get("source") == "n2" and r.get("reenter")
    }
    assert "n7" in reenter_targets
    assert "n16" in reenter_targets
    await eng._advance(
        inst, version, "n2",
        SimpleNamespace(form_data={"department": MINE, "need_purchase": "否"}),
    )
    activated = [
        c.args[2]["id"]
        for c in eng._activate_node.await_args_list
    ]
    assert "n7" in activated
    assert "n16" in activated
    # reenter 传给 activate
    for c in eng._activate_node.await_args_list:
        nid = c.args[2]["id"]
        if nid in {"n7", "n16"}:
            assert c.kwargs.get("allow_reenter") is True
