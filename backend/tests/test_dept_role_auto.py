"""Tests for the dept -> role auto-assignment matcher (app.common.dept_role_auto).

The matching predicate is pure (no DB), so these lock in the correctness-critical
behavior: direct membership, include_children path-prefix matching, prefix
boundary safety, and the empty-path guard.
"""
from app.common.dept_role_auto import _rule_matches


def test_direct_membership_match():
    # 用户直接在规则部门下
    assert _rule_matches({"d1"}, ["/A/"], "d1", "/A/", include_children=False) is True


def test_child_department_match_when_enabled():
    # 用户在子部门 /A/B/，规则针对 /A/ 且含子部门
    assert _rule_matches({"d2"}, ["/A/B/"], "d1", "/A/", include_children=True) is True


def test_child_department_no_match_when_disabled():
    # 同上但不含子部门 -> 不命中
    assert _rule_matches({"d2"}, ["/A/B/"], "d1", "/A/", include_children=False) is False


def test_empty_rule_path_never_matches_everything():
    # 规则部门路径为空串时不得前缀匹配到所有人
    assert _rule_matches({"d2"}, ["/A/B/"], "d1", "", include_children=True) is False
    assert _rule_matches({"d2"}, ["/A/B/"], "d1", None, include_children=True) is False


def test_sibling_prefix_boundary_is_safe():
    # /A/ 不应命中 /AB/(仅字符前缀但非父子)——路径以 / 结尾做边界
    assert _rule_matches({"d4"}, ["/AB/"], "d1", "/A/", include_children=True) is False


def test_no_overlap():
    assert _rule_matches({"d3"}, ["/X/Y/"], "d1", "/A/", include_children=True) is False


def test_path_without_trailing_slash_is_normalized():
    # 规则路径未以 / 结尾也应正确按父子边界匹配
    assert _rule_matches({"d2"}, ["/A/B/"], "d1", "/A", include_children=True) is True
    assert _rule_matches({"d4"}, ["/AB/"], "d1", "/A", include_children=True) is False
