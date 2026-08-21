"""驳回后节点状态 / 流程动态展示回归。"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _ni(**kw):
    base = dict(
        id="ni-1",
        node_def_id="approval_finance",
        node_name="财务审核",
        node_type="approval",
        status="running",
        started_at=datetime(2026, 8, 3, 7, 34, 10, tzinfo=timezone.utc),
        completed_at=None,
        created_at=datetime(2026, 8, 3, 7, 34, 10, tzinfo=timezone.utc),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _log(**kw):
    base = dict(
        node_instance_id="ni-1",
        action="reject",
        actor_id="u1",
        actor_name="李焱焱",
        opinion=None,
        created_at=datetime(2026, 8, 3, 7, 34, 25, tzinfo=timezone.utc),
    )
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_build_flow_steps_maps_stale_running_reject_to_rejected():
    """历史数据：流程已驳回但节点仍 running 时，流程动态应显示「已驳回」而非「处理中」。"""
    from app.domains.lowcode.workflow_service import _build_flow_steps

    db = AsyncMock()
    # User name lookup
    result = MagicMock()
    result.all.return_value = [("u1", "李焱焱", "li")]
    db.execute.return_value = result

    steps = await _build_flow_steps(
        db,
        nodes=[_ni()],
        tasks=[],
        logs=[_log()],
        process_status="rejected",
    )
    assert len(steps) == 1
    assert steps[0]["status"] == "rejected"
    assert steps[0]["status_text"] == "已驳回"
    assert steps[0]["is_current"] is False
    assert steps[0]["action"] == "reject"


@pytest.mark.asyncio
async def test_build_flow_steps_shows_cc_recipients():
    """抄送节点应展示被抄送人姓名（来自 wf_process_cc）。"""
    from app.domains.lowcode.workflow_service import _build_flow_steps

    cc_ni = _ni(
        id="ni-cc",
        node_def_id="cc_1",
        node_name="抄送节点",
        node_type="cc",
        status="completed",
        completed_at=datetime(2026, 8, 15, 10, 45, 50, tzinfo=timezone.utc),
    )
    db = AsyncMock()
    cc_result = MagicMock()
    cc_result.all.return_value = [("ni-cc", "u-wang"), ("ni-cc", "u-li")]
    user_result = MagicMock()
    user_result.all.return_value = [
        ("u-wang", "王东期", "wang"),
        ("u-li", "李四", "li"),
    ]
    db.execute = AsyncMock(side_effect=[cc_result, user_result])

    steps = await _build_flow_steps(db, nodes=[cc_ni], tasks=[], logs=[], process_status="running")
    assert len(steps) == 1
    assert steps[0]["node_type"] == "cc"
    assert steps[0]["handler_name"] == "系统"
    assert steps[0]["action"] == "cc"
    assert [a["name"] for a in steps[0]["assignees"]] == ["王东期", "李四"]


@pytest.mark.asyncio
async def test_build_flow_steps_transfer_shows_pending_assignee():
    """转交后流程动态应显示接收人为当前负责人，并保留转交人意见。"""
    from app.domains.lowcode.workflow_service import _build_flow_steps

    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [
        ("u-from", "王东明", "wang"),
        ("u-to", "刘松潮", "liu"),
    ]
    db.execute.return_value = result

    task = SimpleNamespace(
        id="t1",
        node_instance_id="ni-1",
        assignee_id="u-to",
        status="pending",
    )
    steps = await _build_flow_steps(
        db,
        nodes=[_ni(node_name="设计审批1")],
        tasks=[task],
        logs=[_log(
            action="transfer",
            actor_id="u-from",
            actor_name="王东明",
            opinion="1、供货范围以认可图纸为准;",
        )],
        process_status="running",
    )
    assert len(steps) == 1
    assert steps[0]["status"] == "running"
    assert steps[0]["is_current"] is True
    assert steps[0]["handler_name"] == "刘松潮"
    assert steps[0]["action"] == "pending"
    assert "王东明转交" in (steps[0]["opinion"] or "")
    assert "供货范围" in (steps[0]["opinion"] or "")


@pytest.mark.asyncio
async def test_build_flow_steps_auto_approve_shows_system():
    """自动通过节点应显示系统处理人与自动通过意见。"""
    from app.domains.lowcode.workflow_service import _build_flow_steps

    auto_ni = _ni(
        id="ni-auto",
        node_def_id="n1",
        node_name="业务经理审批",
        status="completed",
        completed_at=datetime(2026, 8, 19, 7, 0, 0, tzinfo=timezone.utc),
        config={"auto_approve": True},
    )
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result

    steps = await _build_flow_steps(
        db,
        nodes=[auto_ni],
        tasks=[],
        logs=[_log(
            node_instance_id="ni-auto",
            action="auto_approve",
            actor_name="系统",
            opinion="节点「业务经理审批」无审批人，自动通过",
        )],
        process_status="running",
    )
    assert len(steps) == 1
    assert steps[0]["action"] == "auto_approve"
    assert steps[0]["handler_name"] == "系统"
    assert "业务经理审批" in (steps[0]["opinion"] or "")


@pytest.mark.asyncio
async def test_reject_flow_closes_running_nodes():
    """_reject_flow 必须把 running 节点置为 rejected，避免 UI 卡住处理中。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    eng = WorkflowEngine(db=AsyncMock(), tenant_id="t")
    eng._queue = MagicMock()
    eng._complete_instance = AsyncMock()

    task = SimpleNamespace(id="t1", status="pending")
    node = SimpleNamespace(id="ni-1", status="running", completed_at=None)
    inst = SimpleNamespace(id="pi-1")

    # 两次 execute：先查 pending tasks，再查 running nodes
    task_result = MagicMock()
    task_result.scalars.return_value.all.return_value = [task]
    node_result = MagicMock()
    node_result.scalars.return_value.all.return_value = [node]
    eng.db.execute = AsyncMock(side_effect=[task_result, node_result])

    await eng._reject_flow(inst, reason="资料不全")

    assert task.status == "cancelled"
    assert node.status == "rejected"
    assert node.completed_at is not None
    eng._complete_instance.assert_awaited_once_with(inst, "rejected", reason="资料不全")
