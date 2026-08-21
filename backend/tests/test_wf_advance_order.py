"""并行出边：选路（谁亮）与激活序（先走谁）分离。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domains.lowcode.workflow_engine import (
    ADVANCE_PHASE_CORE,
    ADVANCE_PHASE_END,
    ADVANCE_PHASE_SIDECAR,
    WorkflowEngine,
)
from app.domains.lowcode.workflow_service import _drawing_flow_graph


def _ver(nodes, routes):
    return SimpleNamespace(node_definitions=nodes, route_definitions=routes)


def test_five_parallel_activate_order_1_to_5():
    """五条并行审批都要亮；activate_order 标明 1→2→3→4→5。"""
    nodes = [{"id": "start", "type": "start", "name": "发起"}]
    routes = []
    # 故意打乱连线定义顺序，只靠 activate_order 体现先后
    for i in (3, 1, 5, 2, 4):
        nodes.append({"id": f"n{i}", "type": "approval", "name": f"节点{i}"})
        routes.append({
            "id": f"r{i}", "source": "start", "target": f"n{i}",
            "activate_order": i,
        })
    nodes.append({"id": "end", "type": "end", "name": "结束"})
    eng = WorkflowEngine(db=None, tenant_id="t")
    batch = eng.explain_advance_batch(_ver(nodes, routes), "start", {})
    assert [x["id"] for x in batch] == ["n1", "n2", "n3", "n4", "n5"]
    assert [x["seq"] for x in batch] == [1, 2, 3, 4, 5]
    assert all(x["phase"] == ADVANCE_PHASE_CORE for x in batch)
    # 选路仍然五条都命中（并行，不是互斥只走一条）
    assert set(eng._next_targets(_ver(nodes, routes), "start", {})) == {
        "n1", "n2", "n3", "n4", "n5",
    }


def test_core_before_cc_even_if_cc_activate_order_is_1():
    """抄送写 activate_order=1 也不能排到审批前面（相位硬规则）。"""
    nodes = [
        {"id": "start", "type": "start", "name": "发起"},
        {"id": "n1", "type": "approval", "name": "开票"},
        {"id": "cc1", "type": "cc", "name": "已提交"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes = [
        {"id": "r_cc", "source": "start", "target": "cc1", "always": True, "activate_order": 1},
        {"id": "r_n1", "source": "start", "target": "n1", "activate_order": 9},
    ]
    eng = WorkflowEngine(db=None, tenant_id="t")
    batch = eng.explain_advance_batch(_ver(nodes, routes), "start", {})
    assert [x["id"] for x in batch] == ["n1", "cc1"]
    assert batch[0]["phase"] == ADVANCE_PHASE_CORE
    assert batch[1]["phase"] == ADVANCE_PHASE_SIDECAR


def test_end_last_in_same_batch():
    nodes = [
        {"id": "start", "type": "start", "name": "发起"},
        {"id": "cc1", "type": "cc", "name": "抄送"},
        {"id": "end", "type": "end", "name": "结束"},
        {"id": "n1", "type": "approval", "name": "审批"},
    ]
    routes = [
        {"id": "r_end", "source": "start", "target": "end"},
        {"id": "r_cc", "source": "start", "target": "cc1", "always": True},
        {"id": "r_n1", "source": "start", "target": "n1"},
    ]
    eng = WorkflowEngine(db=None, tenant_id="t")
    batch = eng.explain_advance_batch(_ver(nodes, routes), "start", {})
    assert [x["id"] for x in batch] == ["n1", "cc1", "end"]
    assert batch[-1]["phase"] == ADVANCE_PHASE_END


def test_should_invent_end_rules():
    """无在途时：纯旁路抄送应收尾（并行收敛）；有主链未 skip 则不发明 end。"""
    eng = WorkflowEngine(db=None, tenant_id="t")
    nodes = {
        "n7": {"id": "n7", "type": "approval", "name": "总工"},
        "n5": {"id": "n5", "type": "approval", "name": "设计指派"},
        "cc1": {"id": "cc1", "type": "cc", "name": "抄送"},
        "end": {"id": "end", "type": "end", "name": "结束"},
    }
    from_n7 = nodes["n7"]
    # 并行支路收敛：只剩抄送且无在途 → 收尾
    assert eng._should_invent_end(
        from_n7, ["cc1"], nodes, has_live_work=False, skipped_reactivate=False,
    ) is True
    assert eng._should_invent_end(
        from_n7, ["n5", "cc1"], nodes, has_live_work=False, skipped_reactivate=False,
    ) is False
    assert eng._should_invent_end(
        from_n7, ["n5"], nodes, has_live_work=False, skipped_reactivate=True,
    ) is True
    assert eng._should_invent_end(
        from_n7, [], nodes, has_live_work=False, skipped_reactivate=False,
    ) is True
    assert eng._should_invent_end(
        from_n7, ["cc1"], nodes, has_live_work=True, skipped_reactivate=False,
    ) is False


def test_await_end_mark_clear():
    """结束被挡住时记 await_end，收敛后可识别。"""
    eng = WorkflowEngine(db=None, tenant_id="t")
    inst = SimpleNamespace(pending_joins=None)
    eng._mark_await_end(inst)
    eng._mark_await_end(inst)  # 幂等
    assert eng._has_await_end(inst)
    assert isinstance(inst.pending_joins, list)
    assert sum(1 for x in inst.pending_joins if isinstance(x, dict) and x.get("await_end")) == 1
    eng._clear_await_end(inst)
    assert not eng._has_await_end(inst)
    assert inst.pending_joins is None


def test_as_list_unwraps_jdy_person_dict():
    from app.domains.lowcode.approver_resolver import ApproverResolver

    assert ApproverResolver._as_list({"username": "013807685436426800", "nickname": "郑志颖"}) == [
        "013807685436426800",
    ]
    assert ApproverResolver._as_list([
        {"id": "u1"}, "u2", {"nickname": "张三"},
    ]) == ["u1", "u2", "张三"]
    assert ApproverResolver._as_list("") == []
    assert ApproverResolver._as_list(None) == []


def test_specified_rule_has_value():
    eng = WorkflowEngine(db=None, tenant_id="t")
    assert eng._specified_rule_has_value(
        {"type": "specified_user", "value": "013807685436426800"},
    )
    assert eng._specified_rule_has_value(
        {"type": "specified_user", "value": {"username": "x", "nickname": "甲"}},
    )
    assert not eng._specified_rule_has_value({"type": "specified_user", "value": ""})
    assert not eng._specified_rule_has_value({"type": "specified_role", "value": "sales"})
    assert not eng._specified_rule_has_value(None)


def test_invoice_start_batch_finance_then_cc():
    graph = _drawing_flow_graph("invoice_application")
    assert graph is not None
    nodes, routes = graph
    eng = WorkflowEngine(db=None, tenant_id="t")
    batch = eng.explain_advance_batch(_ver(nodes, routes), "start", {})
    ids = [x["id"] for x in batch]
    assert ids[0] == "n1"
    assert "cc_sales_submit" in ids
    assert ids.index("n1") < ids.index("cc_sales_submit")


@pytest.mark.asyncio
async def test_advance_five_parallel_calls_in_activate_order():
    nodes = [{"id": "start", "type": "start", "name": "发起"}]
    routes = []
    for i in (4, 2, 5, 1, 3):
        nodes.append({"id": f"n{i}", "type": "approval", "name": f"节点{i}"})
        routes.append({
            "id": f"r{i}", "source": "start", "target": f"n{i}",
            "activate_order": i,
        })
    version = _ver(nodes, routes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    order: list[str] = []

    async def _activate(_inst, _version, node, _ctx, allow_reenter=False):
        order.append(node["id"])

    eng._activate_node = AsyncMock(side_effect=_activate)
    await eng._advance(
        SimpleNamespace(status="running"), version, "start", SimpleNamespace(form_data={}),
    )
    assert order == ["n1", "n2", "n3", "n4", "n5"]
