"""多入边审批节点的隐式汇聚（对齐简道云条件汇入语义）。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def test_can_reach_parallel_branches_converge():
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {"source": "fork", "target": "a"},
        {"source": "fork", "target": "b"},
        {"source": "a", "target": "join"},
        {"source": "b", "target": "join"},
        {"source": "b", "target": "other"},
    ]
    version = SimpleNamespace(route_definitions=routes, node_definitions=[])
    eng = WorkflowEngine(db=None, tenant_id="t")
    assert eng._can_reach(version, "a", "join")
    assert eng._can_reach(version, "b", "join")
    assert not eng._can_reach(version, "a", "other")
    assert not eng._can_reach(version, "other", "join")


def test_incoming_count():
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {"source": "n1", "target": "c"},
        {"source": "n2", "target": "c"},
        {"source": "n3", "target": "d"},
    ]
    version = SimpleNamespace(route_definitions=routes, node_definitions=[])
    eng = WorkflowEngine(db=None, tenant_id="t")
    assert eng._incoming_count(version, "c") == 2
    assert eng._incoming_count(version, "d") == 1


@pytest.mark.asyncio
async def test_activate_approval_defers_when_other_branch_can_reach():
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {"source": "a", "target": "join"},
        {"source": "b", "target": "join"},
    ]
    nodes = [
        {"id": "join", "type": "approval", "name": "销售订单登记"},
    ]
    version = SimpleNamespace(
        route_definitions=routes,
        node_definitions=nodes,
        approver_rules=[],
    )
    inst = SimpleNamespace(
        id="pi1", biz_type="form_instance", biz_id=None, status="running", pending_joins=None,
    )
    node = nodes[0]

    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    eng._other_running_can_reach = AsyncMock(return_value=True)
    eng._log = MagicMock()
    eng.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: None),
    )

    await eng._activate_approval(inst, version, node, SimpleNamespace(form_data={}))
    eng._log.assert_called_once()
    assert eng._log.call_args[0][4] == "defer_convergence"


@pytest.mark.asyncio
async def test_other_running_can_reach_detects_parallel_branch():
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {"source": "a", "target": "join"},
        {"source": "b", "target": "join"},
    ]
    version = SimpleNamespace(route_definitions=routes, node_definitions=[])
    inst = SimpleNamespace(id="pi1")
    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    eng.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: MagicMock(all=lambda: ["b"])),
    )
    assert await eng._other_running_can_reach(inst, version, "join") is True
    eng.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: MagicMock(all=lambda: ["x"])),
    )
    assert await eng._other_running_can_reach(inst, version, "join") is False


@pytest.mark.asyncio
async def test_activate_approval_defers_during_reenter_session():
    """退回/重提后 reenter_session 仍应对多入边节点做隐式汇聚。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {"source": "a", "target": "join"},
        {"source": "b", "target": "join"},
    ]
    nodes = [{"id": "join", "type": "approval", "name": "总经理审批"}]
    version = SimpleNamespace(
        route_definitions=routes,
        node_definitions=nodes,
        approver_rules=[],
    )
    inst = SimpleNamespace(
        id="pi1",
        biz_type="form_instance",
        biz_id=None,
        status="running",
        pending_joins=[{"reenter_session": True}],
    )
    node = nodes[0]

    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    eng._other_running_can_reach = AsyncMock(return_value=True)
    eng._log = MagicMock()
    eng.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: None),
    )

    await eng._activate_approval(
        inst, version, node, SimpleNamespace(form_data={}), allow_reenter=True,
    )
    eng._log.assert_called_once()
    assert eng._log.call_args[0][4] == "defer_convergence"


@pytest.mark.asyncio
async def test_activate_approval_single_incoming_no_defer():
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [{"source": "a", "target": "c"}]
    nodes = [{"id": "c", "type": "approval", "name": "单入边"}]
    version = SimpleNamespace(
        route_definitions=routes,
        node_definitions=nodes,
        approver_rules=[],
    )
    inst = SimpleNamespace(
        id="pi1", biz_type="form_instance", biz_id=None, status="running", pending_joins=None,
    )
    node = nodes[0]

    eng = WorkflowEngine(db=MagicMock(), tenant_id="t")
    eng._resolve_approvers = AsyncMock(return_value=["u1"])
    eng._log = MagicMock()
    eng.db.add = MagicMock()
    eng.db.flush = AsyncMock()
    eng.db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))

    await eng._activate_approval(inst, version, node, SimpleNamespace(form_data={}))
    assert not any(c[0][4] == "defer_convergence" for c in eng._log.call_args_list)
