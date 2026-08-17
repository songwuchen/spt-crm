"""表单列表筛选：部门/人员按名称解析。"""
from __future__ import annotations

from app.domains.lowcode.service import (
    _UUID_RE,
    _flatten_filter_values,
    _form_data_filter_clause,
    _normalize_instance_filters,
)


def test_uuid_detect():
    assert _UUID_RE.match("d017a32d-91e1-44fb-bda5-96ae3994a897")
    assert not _UUID_RE.match("砂石")


def test_flatten_filter_values():
    assert _flatten_filter_values("砂石") == ["砂石"]
    assert _flatten_filter_values(["a", " b ", ""]) == ["a", "b"]
    assert _flatten_filter_values(None) == []


def test_normalize_contains_rule():
    match, rules = _normalize_instance_filters({
        "match": "all",
        "rules": [{"field": "department", "op": "contains", "value": "砂石"}],
    })
    assert match == "all"
    assert rules == [{"field": "department", "op": "contains", "value": "砂石"}]


def test_plain_contains_still_works_for_text():
    clause = _form_data_filter_clause({
        "field": "dept_code", "op": "contains", "value": "03",
    })
    assert clause is not None
