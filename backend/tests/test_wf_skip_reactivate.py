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


def test_next_targets_exclusive_multi_blank_takes_first_else_only():
    """互斥组内多条无条件边（条件被清掉的假 else）只走第一条，避免串行双开。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    routes = [
        {"id": "r_10", "source": "start", "target": "n1", "exclusive_group": "ex_start"},
        {"id": "r_19", "source": "start", "target": "n10",
         "condition": None, "exclusive_group": "ex_start"},
        {"id": "r_20", "source": "start", "target": "n11",
         "condition": None, "exclusive_group": "ex_start"},
    ]
    version = SimpleNamespace(route_definitions=routes, node_definitions=[])
    eng = WorkflowEngine(db=None, tenant_id="t")
    assert eng._next_targets(version, "start", {}) == ["n1"]


def test_clean_unknown_dept_drops_route_when_condition_empty():
    """部门条件值全无效时删除连线，而不是 condition=null 变成假 else。"""
    from app.domains.lowcode.jdy_id_remap import clean_unknown_dept_ids_in_routes

    routes = [
        {"id": "r_else", "source": "start", "target": "n1", "exclusive_group": "ex"},
        {
            "id": "r_cond", "source": "start", "target": "n10",
            "exclusive_group": "ex",
            "condition": {
                "field": "department", "operator": "in",
                "value": ["dead-jdy-id"],
            },
        },
    ]
    cleaned, stats = clean_unknown_dept_ids_in_routes(routes, valid_dept_ids={"crm-uuid"})
    assert stats["routes_dropped"] == 1
    assert [r["id"] for r in cleaned] == ["r_else"]
    assert cleaned[0].get("condition") is None


def test_flow_exclusive_group_multi_blank_detects_quote_corruption():
    from app.domains.lowcode.workflow_service import _flow_exclusive_group_multi_blank

    bad = [
        {"id": "r_10", "source": "start", "target": "n1", "exclusive_group": "ex_start"},
        {"id": "r_19", "source": "start", "target": "n10",
         "condition": None, "exclusive_group": "ex_start"},
    ]
    good = [
        {"id": "r_10", "source": "start", "target": "n1", "exclusive_group": "ex_start"},
        {
            "id": "r_19", "source": "start", "target": "n10",
            "exclusive_group": "ex_start",
            "condition": {"field": "department", "operator": "eq", "value": "x"},
        },
    ]
    assert _flow_exclusive_group_multi_blank(bad) is True
    assert _flow_exclusive_group_multi_blank(good) is False


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
    done_ni = SimpleNamespace(config={})
    done_hit = MagicMock()
    done_hit.scalar_one_or_none.return_value = done_ni
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
async def test_specified_user_unresolved_hangs_without_auto_approve():
    """写了指定人却解析不到：挂起节点，禁止 auto_approve 吃掉主链。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    eng = WorkflowEngine(db=AsyncMock(), tenant_id="t")
    eng._queue = MagicMock()
    eng._log = MagicMock()
    eng._resolve_approvers = AsyncMock(return_value=[])
    eng._advance = AsyncMock()
    eng.db.flush = AsyncMock()

    running_miss = MagicMock()
    running_miss.scalar_one_or_none.return_value = None
    eng.db.execute = AsyncMock(return_value=running_miss)

    inst = SimpleNamespace(id="pi-1", biz_type="form", biz_id=None, tenant_id="t")
    node = {
        "id": "n5", "type": "approval", "name": "设计指派安排",
        "approver_rule": {"type": "specified_user", "value": "013807685436426800"},
        "empty_strategy": "auto_approve",
    }
    version = SimpleNamespace(node_definitions=[node], route_definitions=[], approver_rules=[])
    ctx = SimpleNamespace(form_data={}, initiator_id="u1", nominated={})

    await eng._activate_approval(inst, version, node, ctx)

    eng._advance.assert_not_awaited()
    eng.db.add.assert_called()
    eng._log.assert_called()
    assert eng._log.call_args[0][4] == "unresolved_approver"


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


@pytest.mark.asyncio
async def test_activate_approval_reopens_auto_approved_when_approver_now_resolves():
    """曾因无审批人 auto_approve 的节点，表单补人后应允许重开（售前人员协调）。"""
    from app.domains.lowcode.workflow_engine import WorkflowEngine

    eng = WorkflowEngine(db=AsyncMock(), tenant_id="t")
    eng._queue = MagicMock()
    eng._log = MagicMock()
    eng._resolve_approvers = AsyncMock(return_value=["u-wang"])
    eng._advance = AsyncMock()
    eng.db.flush = AsyncMock()

    running_miss = MagicMock()
    running_miss.scalar_one_or_none.return_value = None
    done_ni = SimpleNamespace(config={"auto_approve": True})
    done_hit = MagicMock()
    done_hit.scalar_one_or_none.return_value = done_ni
    eng.db.execute = AsyncMock(side_effect=[running_miss, done_hit])

    inst = SimpleNamespace(id="pi-1", biz_type="form", biz_id=None, tenant_id="t")
    node = {
        "id": "n3", "type": "approval", "name": "人员协调",
        "approver_rule": {"type": "form_field_person", "value": "staff_coordination"},
        "multi_mode": "or_sign",
    }
    version = SimpleNamespace(node_definitions=[node], route_definitions=[])
    ctx = SimpleNamespace(form_data={"staff_coordination": ["u-wang"]}, initiator_id="u1", nominated={})

    await eng._activate_approval(inst, version, node, ctx)

    eng._resolve_approvers.assert_awaited()
    eng.db.add.assert_called()
    assert not any(c[0][4] == "skip_reactivate" for c in eng._log.call_args_list)
