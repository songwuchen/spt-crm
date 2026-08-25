"""发起人手动结束：清掉驳回/撤回后的修订待办。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import BusinessException


def _engine():
    from app.domains.lowcode.workflow_engine import WorkflowEngine
    db = AsyncMock()
    eng = WorkflowEngine(db, "t1")
    eng._cancel_initiator_revise_todos = AsyncMock()
    eng._log = MagicMock()
    eng._audit = AsyncMock()
    eng.flush_notifications = AsyncMock()
    return eng, db


@pytest.mark.asyncio
async def test_end_process_rejects_running():
    eng, db = _engine()
    inst = SimpleNamespace(
        id="p1", status="running", initiator_id="u1", tenant_id="t1",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = inst
    db.execute.return_value = result
    with pytest.raises(BusinessException) as ei:
        await eng.end_process("p1", {"sub": "u1"})
    assert "仅已驳回、已退回或已撤回" in str(ei.value.message)


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
