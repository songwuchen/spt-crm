"""手动结束流程：修订待办关闭 + 进行中终止。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import BusinessException


def _engine():
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    db = AsyncMock()
    eng = WorkflowEngine(db, "t1")
    eng._cancel_initiator_revise_todos = AsyncMock()
    eng._terminate_running_process = AsyncMock()
    eng._log = MagicMock()
    eng._audit = AsyncMock()
    eng.flush_notifications = AsyncMock()
    return eng, db


@pytest.mark.asyncio
async def test_end_process_running_delegates_to_terminate():
    eng, db = _engine()
    inst = SimpleNamespace(
        id="p1", status="running", initiator_id="u1", tenant_id="t1",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = inst
    db.execute.return_value = result
    await eng.end_process("p1", {"sub": "u1"})
    eng._terminate_running_process.assert_awaited_once_with(inst, {"sub": "u1"}, reason=None)


@pytest.mark.asyncio
async def test_end_process_rejects_completed():
    eng, db = _engine()
    inst = SimpleNamespace(
        id="p1", status="completed", initiator_id="u1", tenant_id="t1",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = inst
    db.execute.return_value = result
    with pytest.raises(BusinessException) as ei:
        await eng.end_process("p1", {"sub": "u1"})
    assert "不可结束" in str(ei.value.message)


@pytest.mark.asyncio
async def test_end_process_forbidden_for_outsider():
    eng, db = _engine()
    inst = SimpleNamespace(
        id="p1", status="rejected", initiator_id="u1", tenant_id="t1",
    )
    inst_result = MagicMock()
    inst_result.scalar_one_or_none.return_value = inst
    empty_assignees = MagicMock()
    empty_assignees.scalars.return_value.all.return_value = []
    db.execute.side_effect = [inst_result, empty_assignees]
    with pytest.raises(BusinessException) as ei:
        await eng.end_process("p1", {"sub": "other"})
    assert "仅发起人" in str(ei.value.message)


@pytest.mark.asyncio
async def test_end_process_ok_for_initiator():
    eng, db = _engine()
    inst = SimpleNamespace(
        id="p1", status="rejected", initiator_id="u1", tenant_id="t1",
    )
    inst_result = MagicMock()
    inst_result.scalar_one_or_none.return_value = inst
    empty_assignees = MagicMock()
    empty_assignees.scalars.return_value.all.return_value = []
    db.execute.side_effect = [inst_result, empty_assignees]
    await eng.end_process("p1", {"sub": "u1", "real_name": "发起人"})
    eng._cancel_initiator_revise_todos.assert_awaited_once_with("p1")
    eng._log.assert_called_once()
    assert eng._log.call_args.args[4] == "end_process"
    db.commit.assert_awaited()


def _terminate_engine():
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    db = AsyncMock()
    eng = WorkflowEngine(db, "t1")
    eng._log = MagicMock()
    eng._audit = AsyncMock()
    eng.flush_notifications = AsyncMock()
    eng._queue = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    return eng, db


@pytest.mark.asyncio
async def test_terminate_running_forbidden_for_outsider():
    eng, _db = _terminate_engine()
    inst = SimpleNamespace(
        id="p1", status="running", initiator_id="u1", tenant_id="t1",
        form_instance_id=None, biz_type=None, biz_id=None,
    )
    with pytest.raises(BusinessException) as ei:
        await eng._terminate_running_process(inst, {"sub": "other", "permissions": []})
    assert "仅发起人" in str(ei.value.message)


@pytest.mark.asyncio
async def test_terminate_running_ok_for_initiator():
    eng, db = _terminate_engine()
    inst = SimpleNamespace(
        id="p1", status="running", initiator_id="u1", tenant_id="t1",
        form_instance_id=None, biz_type=None, biz_id=None,
        pending_joins={},
    )
    empty_nis = MagicMock()
    empty_nis.scalars.return_value.all.return_value = []
    empty_tasks = MagicMock()
    empty_tasks.scalars.return_value.all.return_value = []
    db.execute.side_effect = [empty_nis, empty_tasks]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.domains.lowcode.wf_notify.enqueue_wf_event",
            AsyncMock(),
        )
        mp.setattr(
            "app.domains.lowcode.shipment_notice_events.emit_from_process",
            AsyncMock(),
        )
        await eng._terminate_running_process(inst, {"sub": "u1", "permissions": []})

    assert inst.status == "terminated"
    eng._log.assert_called_once()
    assert eng._log.call_args.args[4] == "terminate"
    db.commit.assert_awaited()
