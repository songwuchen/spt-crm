# -*- coding: utf-8 -*-
"""通用转交：支持多人。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.lowcode.workflow_engine import WorkflowEngine


def test_normalize_transfer_targets_single_and_multi():
    assert WorkflowEngine._normalize_transfer_targets(None) == []
    assert WorkflowEngine._normalize_transfer_targets("") == []
    assert WorkflowEngine._normalize_transfer_targets("u1") == ["u1"]
    assert WorkflowEngine._normalize_transfer_targets(["u1", "u2", "u1", "", None]) == ["u1", "u2"]
    assert WorkflowEngine._normalize_transfer_targets(("a", "b")) == ["a", "b"]


@pytest.mark.asyncio
async def test_cancel_or_sign_siblings_except_keeps_only_transfer_targets():
    """转交后撤销同节点其他或签待办。"""
    t_keep = SimpleNamespace(
        id="t-cao", assignee_id="u-cao", status="pending", created_at=1,
    )
    t_wang = SimpleNamespace(
        id="t-wang", assignee_id="u-wang", status="pending", created_at=2,
    )
    t_duan = SimpleNamespace(
        id="t-duan", assignee_id="u-duan", status="pending", created_at=3,
    )
    t_zhang = SimpleNamespace(
        id="t-zhang", assignee_id="u-zhang", status="pending", created_at=4,
    )
    siblings = [t_keep, t_wang, t_duan, t_zhang]

    result = MagicMock()
    result.scalars.return_value.all.return_value = siblings
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()

    engine = WorkflowEngine(db, "tenant-1")
    engine._queue = MagicMock()

    await engine._cancel_or_sign_siblings_except(
        "ni-9", {"u-cao", "u-wang"}, keep_task_ids={"t-cao"},
    )

    assert t_duan.status == "cancelled"
    assert t_zhang.status == "cancelled"
    assert t_keep.status == "pending"
    assert t_wang.status == "pending"
    engine._queue.assert_called_once()
    assert engine._queue.call_args[0][0] == "todos_done"
    assert set(engine._queue.call_args[0][1]) == {"t-duan", "t-zhang"}
