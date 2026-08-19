"""audit_diff 单元测试。"""
from app.common.audit_diff import (
    compute_dict_changes,
    compute_entity_changes,
    enrich_changes_with_labels,
    serialize_value,
)


class _FakeEntity:
    name = "旧名"
    review_json = {"risk_level": "低"}


def test_serialize_value():
    assert serialize_value(None) is None
    assert serialize_value("abc") == "abc"


def test_compute_dict_changes():
    changes = compute_dict_changes({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4})
    assert "a" not in changes
    assert changes["b"] == {"old": 2, "new": 3}
    assert changes["c"] == {"old": None, "new": 4}


def test_compute_entity_changes_json_field():
    entity = _FakeEntity()
    changes = compute_entity_changes(
        entity,
        {"name": "新名", "review_json": {"risk_level": "高", "note": "x"}},
        json_fields={"review_json"},
    )
    assert changes["name"] == {"old": "旧名", "new": "新名"}
    assert changes["review_json.risk_level"] == {"old": "低", "new": "高"}
    assert changes["review_json.note"] == {"old": None, "new": "x"}


def test_enrich_changes_with_labels():
    raw = {"company_name": {"old": "A", "new": "B"}}
    out = enrich_changes_with_labels(raw, {"company_name": "公司名称"})
    assert out["company_name"]["label"] == "公司名称"
