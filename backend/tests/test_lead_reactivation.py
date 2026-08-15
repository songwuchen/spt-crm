"""线索 180 天重激活：纯逻辑单测（不打库）。"""
from types import SimpleNamespace

from app.domains.lead.reactivation import (
    CLOSE_PROJECT_STATUSES,
    REACT_AWAITING_FILLER,
    REACT_AWAITING_REPORTER,
    _resolve_assignee,
    lead_confirm_assignee_id,
    mark_cycle_reset,
    normalize_config,
    should_skip_reporter,
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
