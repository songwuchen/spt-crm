"""退回发起人应置 returned，修订节点显示待修改而非已驳回。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.lowcode.workflow_service import _build_flow_steps


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _mock_db():
    db = AsyncMock()
    empty = MagicMock()
    empty.all.return_value = []
    db.execute = AsyncMock(return_value=empty)
    return db


@pytest.mark.asyncio
async def test_build_flow_steps_revise_shows_pending_not_rejected():
    db = _mock_db()
    revise = SimpleNamespace(
        id="ni-revise",
        node_def_id="__initiator_revise__",
        node_type="revise",
        node_name="修改并重新提交",
        status="running",
        config={},
        started_at=_now(),
        completed_at=None,
        created_at=_now(),
    )
    task = SimpleNamespace(
        id="t1",
        node_instance_id="ni-revise",
        assignee_id="u-init",
        status="pending",
    )
    steps = await _build_flow_steps(
        db, [revise], [task], [], process_status="returned",
    )
    assert len(steps) == 1
    assert steps[0]["status"] == "running"
    assert steps[0]["status_text"] == "待修改"
    assert steps[0]["is_current"] is True


@pytest.mark.asyncio
async def test_build_flow_steps_return_action_status_text():
    db = _mock_db()
    approval = SimpleNamespace(
        id="ni-n2",
        node_def_id="n2",
        node_type="approval",
        node_name="财务核价",
        status="completed",
        config={},
        started_at=_now(),
        completed_at=_now(),
        created_at=_now(),
    )
    log = SimpleNamespace(
        id="lg1",
        node_instance_id="ni-n2",
        action="return",
        actor_name="张光",
        actor_id="u1",
        opinion="请修改",
        created_at=_now(),
        updated_at=_now(),
    )
    steps = await _build_flow_steps(
        db, [approval], [], [log], process_status="returned",
    )
    assert len(steps) == 1
    assert steps[0]["status_text"] == "已退回"
    assert steps[0]["action"] == "return"


def test_fmt_duration_verbose_like_jdy():
    from datetime import datetime, timedelta, timezone
    from app.domains.lowcode.workflow_service import _build_process_end_step, _fmt_duration_verbose

    tz = timezone.utc
    start = datetime(2026, 8, 17, 18, 10, 6, tzinfo=tz)
    end = start + timedelta(days=4, hours=21, minutes=3, seconds=8)
    assert _fmt_duration_verbose(start, end) == "4天21时3分8秒"

    inst = SimpleNamespace(
        id="pi1",
        status="completed",
        started_at=start,
        created_at=start,
        completed_at=end,
    )
    step = _build_process_end_step(inst)
    assert step is not None
    assert step["node_name"] == "流程结束"
    assert step["is_process_end"] is True
    assert step["duration"] == "4天21时3分8秒"


def test_build_process_end_step_skips_running():
    from app.domains.lowcode.workflow_service import _build_process_end_step

    inst = SimpleNamespace(
        id="pi2", status="running", started_at=_now(), completed_at=None,
    )
    assert _build_process_end_step(inst) is None
