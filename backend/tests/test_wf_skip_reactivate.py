"""流程引擎：审批节点禁止晚到重复激活 + 缺互斥组的 if/else 兜底。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def test_next_targets_auto_if_else_without_exclusive_group():
    """部门审批式出边漏标 exclusive_group 时，不得市场支持∥总工双开。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {
            "id": "r_market", "source": "n1", "target": "n11",
            "condition": {
                "field": "department", "operator": "in",
                "value": ["sales-dept"],
            },
        },
        {"id": "r_chief", "source": "n1", "target": "n7"},  # else
    ]
    version = SimpleNamespace(route_definitions=routes, node_definitions=[])
    eng = WorkflowEngine(db=None, tenant_id="t")

    assert eng._next_targets(version, "n1", {"department": "sales-dept"}) == ["n11"]
    assert eng._next_targets(version, "n1", {"department": "other"}) == ["n7"]
    assert eng._next_targets(version, "n1", {}) == ["n7"]


def test_next_targets_two_unconditional_still_parallel():
    """两条无条件边仍并行（非 if/else 形态，不误改）。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {"id": "r_a", "source": "n1", "target": "a"},
        {"id": "r_b", "source": "n1", "target": "b"},
    ]
    version = SimpleNamespace(route_definitions=routes, node_definitions=[])
    eng = WorkflowEngine(db=None, tenant_id="t")
    assert set(eng._next_targets(version, "n1", {})) == {"a", "b"}


@pytest.mark.asyncio
async def test_activate_approval_skips_when_already_completed():
    """总工已完成并推进后，晚到的市场支持→总工不得再建第二个总工。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    eng = WorkflowEngine(db=AsyncMock(), tenant_id="t")
    eng._queue = MagicMock()
    eng._log = MagicMock()
    eng._resolve_approvers = AsyncMock(return_value=["u-chief"])

    running_miss = MagicMock()
    running_miss.scalar_one_or_none.return_value = None
    done_hit = MagicMock()
    done_hit.scalar_one_or_none.return_value = "ni-old-completed"
    eng.db.execute = AsyncMock(side_effect=[running_miss, done_hit])

    inst = SimpleNamespace(id="pi-1", biz_type="form", biz_id=None)
    node = {"id": "n7", "type": "approval", "name": "总工审批"}
    ctx = SimpleNamespace(form_data={}, initiator_id="u1", nominated={})

    await eng._activate_approval(inst, SimpleNamespace(), node, ctx)

    eng.db.add.assert_not_called()
    eng._resolve_approvers.assert_not_called()
    eng._log.assert_called()
    assert eng._log.call_args[0][4] == "skip_reactivate"


@pytest.mark.asyncio
async def test_activate_approval_allow_reenter_after_completed():
    """退回重入：即使历史总工已完成，也允许再次激活。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    eng = WorkflowEngine(db=AsyncMock(), tenant_id="t")
    eng._queue = MagicMock()
    eng._log = MagicMock()
    eng._resolve_approvers = AsyncMock(return_value=["u-chief"])
    eng._advance = AsyncMock()
    eng.db.flush = AsyncMock()

    running_miss = MagicMock()
    running_miss.scalar_one_or_none.return_value = None
    eng.db.execute = AsyncMock(side_effect=[running_miss])

    inst = SimpleNamespace(id="pi-1", biz_type="form", biz_id=None, tenant_id="t")
    node = {
        "id": "n7", "type": "approval", "name": "总工审批",
        "approver_rule": {"type": "specified_user", "value": "u-chief"},
        "multi_mode": "or_sign",
    }
    version = SimpleNamespace(node_definitions=[node], route_definitions=[])
    ctx = SimpleNamespace(form_data={}, initiator_id="u1", nominated={})

    await eng._activate_approval(
        inst, version, node, ctx, allow_reenter=True,
    )

    eng.db.add.assert_called()
    eng._resolve_approvers.assert_awaited()
