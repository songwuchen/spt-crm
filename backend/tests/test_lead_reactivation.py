"""线索 180 天重激活：纯逻辑单测（不打库）。"""
from types import SimpleNamespace

from app.domains.lead.reactivation import (
    CLOSE_PROJECT_STATUSES,
    PROGRESS_STATUS,
    REACT_AWAITING_FILLER,
    REACT_AWAITING_REPORTER,
    REACT_NODE_FILLER,
    REACT_NODE_FILLER_SKIP,
    _resolve_assignee,
    ends_reactivation_round,
    lead_confirm_assignee_id,
    mark_cycle_reset,
    needs_intel_review,
    normalize_config,
    reactivation_status_for_node,
    should_skip_reporter,
)
from app.domains.lowcode.workflow_service import (
    _LEAD_REACT_FILLER_NODE_ID,
    _LEAD_REACT_FILLER_SKIP_NODE_ID,
    _flow_is_jdy_lead_reactivation,
    _lead_intel_approver_rule,
    _lead_reactivation_flow_graph,
)


def test_normalize_config_days_and_names():
    cfg = normalize_config({"days": 30, "scan_time": "9:30", "skip_reporter_names": "甲, 乙"})
    assert cfg["days"] == 30
    assert cfg["scan_time"] == "09:30"
    assert cfg["skip_reporter_names"] == ["甲", "乙"]
    assert cfg["enabled"] is True


def test_skip_reporter_by_name():
    cfg = {"skip_reporter_names": ["张贺", "其他人"]}
    lead = SimpleNamespace(reporter_name="张贺", owner_name="甲", created_by_name="乙")
    assert should_skip_reporter(lead, cfg) is True
    lead2 = SimpleNamespace(reporter_name="李四", owner_name="张贺", created_by_name="张贺")
    assert should_skip_reporter(lead2, cfg) is False


def test_lead_confirm_assignee_skips_to_filler():
    cfg = {"skip_reporter_names": ["张贺"]}
    lead = SimpleNamespace(
        reporter_id="r1", reporter_name="张贺",
        created_by_id="c1", owner_id="o1",
    )
    assert lead_confirm_assignee_id(lead, cfg) == "c1"
    normal = SimpleNamespace(
        reporter_id="r1", reporter_name="王五",
        created_by_id="c1", owner_id="o1",
    )
    assert lead_confirm_assignee_id(normal, cfg) == "r1"


def test_lead_confirm_assignee_falls_back_when_reporter_empty():
    """申报人未选时，确认待办回退负责人，避免确认节点 terminate 驳回整单。"""
    lead = SimpleNamespace(
        reporter_id=None, reporter_name=None,
        created_by_id="c1", owner_id="o1",
    )
    assert lead_confirm_assignee_id(lead, {}) == "o1"
    no_owner = SimpleNamespace(
        reporter_id=None, reporter_name=None,
        created_by_id="c1", owner_id=None,
    )
    assert lead_confirm_assignee_id(no_owner, {}) == "c1"


def test_resolve_assignee_skips_to_filler():
    cfg = {"skip_reporter_names": ["张贺"]}
    lead = SimpleNamespace(
        reporter_id="r1", reporter_name="张贺",
        created_by_id="c1", created_by_name="填表人",
        owner_id="o1", owner_name="负责人",
    )
    uid, name, status = _resolve_assignee(lead, prefer_filler=False, cfg=cfg)
    assert uid == "c1"
    assert name == "填表人"
    assert status == REACT_AWAITING_FILLER


def test_resolve_assignee_normal_reporter():
    cfg = {"skip_reporter_names": ["张贺"]}
    lead = SimpleNamespace(
        reporter_id="r1", reporter_name="王五",
        created_by_id="c1", created_by_name="填表人",
        owner_id="o1", owner_name="负责人",
    )
    uid, name, status = _resolve_assignee(lead, prefer_filler=False, cfg=cfg)
    assert uid == "r1"
    assert status == REACT_AWAITING_REPORTER


def test_close_statuses_include_customer_terms():
    assert "暂缓" in CLOSE_PROJECT_STATUSES
    assert "取消" in CLOSE_PROJECT_STATUSES
    assert "落标" in CLOSE_PROJECT_STATUSES


def test_needs_intel_review_only_in_progress():
    assert needs_intel_review("进行中") is True
    assert needs_intel_review("中标") is False
    assert needs_intel_review("已签合同") is False
    assert needs_intel_review("落标") is False


def test_ends_reactivation_round_direct_end_statuses():
    assert ends_reactivation_round("中标") is True
    assert ends_reactivation_round("已签合同") is True
    assert ends_reactivation_round("进行中") is False
    assert ends_reactivation_round("落标") is False
    assert ends_reactivation_round("暂缓") is False


def test_mark_cycle_reset():
    lead = SimpleNamespace(
        cycle_anchor_at=None,
        reactivation_status="pending_review",
        reactivation_notified_at="x",
    )
    mark_cycle_reset(lead)
    assert lead.cycle_anchor_at is not None
    assert lead.reactivation_status == "none"
    assert lead.reactivation_notified_at is None


def test_scan_due_exact_day_like_jdy():
    """到期扫描对齐简道云：精确满 N 天当天（==），非积压全扫。"""
    import inspect
    from app.domains.lead import reactivation as mod
    src = inspect.getsource(mod.scan_and_activate)
    assert "anchor_cn_date == target_date" in src
    assert "activate_on_scan" in src
    assert "anchor_cn_date <= target_date" not in src
    src_activate = inspect.getsource(mod.activate_lead)
    assert "_create_round_record_on_activate" in src_activate


def test_reactivation_status_for_both_filler_nodes():
    assert reactivation_status_for_node(REACT_NODE_FILLER) == REACT_AWAITING_FILLER
    assert reactivation_status_for_node(REACT_NODE_FILLER_SKIP) == REACT_AWAITING_FILLER
    assert reactivation_status_for_node("approval_sales") == REACT_AWAITING_REPORTER


def test_lead_reactivation_flow_has_two_filler_nodes():
    nodes, routes = _lead_reactivation_flow_graph(
        "180天项目激活审批", _lead_intel_approver_rule(), "or_sign", "auto_approve",
    )
    ids = {n["id"] for n in nodes}
    assert _LEAD_REACT_FILLER_SKIP_NODE_ID in ids
    assert _LEAD_REACT_FILLER_NODE_ID in ids
    assert "cc_reporter" in ids
    assert _flow_is_jdy_lead_reactivation(nodes, routes) is True
    by_id = {n["id"]: n for n in nodes}
    assert by_id[_LEAD_REACT_FILLER_SKIP_NODE_ID].get("field_perms")
    assert not by_id[_LEAD_REACT_FILLER_NODE_ID].get("field_perms")
    intel = by_id["approval_intel"]
    assert intel.get("name") == "信息情报部审批"
    intel_fields = {p["field"] for p in (intel.get("field_perms") or [])}
    assert "has_internal_conflict" in intel_fields
    assert "conflict_note" in intel_fields


def test_sync_reactivation_status_uses_node_def_id_string():
    """regression: scalar_one_or_none 返回 str，不可再取 [0]。"""
    import inspect
    from app.domains.lead import reactivation as mod
    src = inspect.getsource(mod.sync_reactivation_status_from_wf)
    assert "row[0]" not in src
    assert "reactivation_status_for_node(node_def_id)" in src


def test_reactivation_uses_separate_workflow():
    """180天激活全链路走 lead_reactivation workflow，不复用申报 lead 审批。"""
    import inspect
    from app.domains.lead import reactivation as mod
    src_activate = inspect.getsource(mod.activate_lead)
    assert "start_reactivation_workflow" in src_activate
    assert "_create_task_and_notify" not in src_activate
    src_intel = inspect.getsource(mod.reactivation_intel_review)
    assert "WF_BIZ_TYPE" in src_intel or "lead_reactivation" in src_intel
    assert "review_status" not in src_intel or "review_status =" not in src_intel
