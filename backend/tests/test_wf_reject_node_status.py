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
