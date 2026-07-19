"""表单规则引擎(后端)单元测试。

重点验证与前端 RuleEngine.ts 对等的语义：条件显隐、条件必填、嵌套条件组、
子表任一行匹配、级联隐藏不动点，以及「被隐藏字段不报必填」这一防死锁行为。
"""
import pytest

from app.domains.lowcode.rule_engine import (
    compute_field_states,
    evaluate_condition,
    validate_required_with_rules,
)


def F(fid, **kw):
    return {"id": fid, "type": kw.pop("type", "text"), "label": kw.pop("label", fid), **kw}


def vis_rule(rid, target, condition, visible=True):
    return {"id": rid, "type": "visibility", "target_field_id": target,
            "condition": condition, "action": {"visible": visible}}


# ===== 操作符 =====

@pytest.mark.parametrize("actual,op,expected,want", [
    ("overseas", "eq", "overseas", True),
    ("overseas", "eq", "domestic", False),
    (5, "eq", "5", True),                      # JS 松散相等：数字与字符串
    (True, "eq", "true", True),
    (None, "is_empty", None, True),
    ("", "is_empty", None, True),
    ([], "is_empty", None, True),
    (0, "is_empty", None, False),              # 0 不算空
    (False, "is_empty", None, False),
    (10, "gt", 5, True),
    ("10", "gt", "5", True),                   # 数字串按数值比，不按字典序
    (None, "gt", 5, False),
    ("", "gt", -1, False),
    ("b", "in", "a,b,c", True),
    ("d", "in", "a,b,c", False),
    (["a", "x"], "in", ["x", "y"], True),
    ("d", "not_in", ["a", "b"], True),
    ("hello world", "contains", "lo w", True),
    (["a", "b"], "contains", "b", True),
    ("hello", "starts_with", "he", True),
    ("hello", "ends_with", "lo", True),
])
def test_operators(actual, op, expected, want):
    cond = {"field": "f", "operator": op, "value": expected}
    assert evaluate_condition(cond, {"f": actual}, {}) is want


# ===== 条件组 =====

def test_nested_condition_groups():
    fields = [F("a"), F("b"), F("c")]
    cond = {"rel": "or", "cond": [
        {"field": "a", "operator": "eq", "value": "1"},
        {"rel": "and", "cond": [
            {"field": "b", "operator": "eq", "value": "2"},
            {"field": "c", "operator": "eq", "value": "3"},
        ]},
    ]}
    sub = {}
    assert evaluate_condition(cond, {"a": "1"}, sub) is True
    assert evaluate_condition(cond, {"b": "2", "c": "3"}, sub) is True
    assert evaluate_condition(cond, {"b": "2", "c": "9"}, sub) is False
    assert evaluate_condition(cond, {}, sub) is False
    assert fields  # 仅表明字段集与条件字段一致


def test_empty_group_follows_rel():
    assert evaluate_condition({"rel": "and", "cond": []}, {}, {}) is False  # 空 cond 走单条件分支
    assert evaluate_condition({}, {}, {}) is False


# ===== 显隐 =====

def test_visibility_rule_toggles_field():
    fields = [F("country_type"), F("country_name")]
    rules = [vis_rule("r1", "country_name",
                      {"field": "country_type", "operator": "eq", "value": "overseas"})]

    st = compute_field_states(fields, {"country_type": "overseas"}, rules)
    assert st["country_name"]["visible"] is True

    st = compute_field_states(fields, {"country_type": "domestic"}, rules)
    assert st["country_name"]["visible"] is False


def test_cascade_hidden_reaches_fixpoint():
    """b 被 a 藏起来后，b 的值不应再让 c 显示（级联隐藏）。"""
    fields = [F("a"), F("b"), F("c")]
    rules = [
        vis_rule("r1", "b", {"field": "a", "operator": "eq", "value": "show"}),
        vis_rule("r2", "c", {"field": "b", "operator": "eq", "value": "yes"}),
    ]
    st = compute_field_states(fields, {"a": "hide", "b": "yes"}, rules)
    assert st["b"]["visible"] is False
    assert st["c"]["visible"] is False, "b 已隐藏，其残留值不应再驱动 c 显示"

    st = compute_field_states(fields, {"a": "show", "b": "yes"}, rules)
    assert st["b"]["visible"] is True
    assert st["c"]["visible"] is True


# ===== 必填 =====

def test_conditional_required():
    fields = [F("country_type"), F("country_name")]
    rules = [{"id": "r1", "type": "required", "target_field_id": "country_name",
              "condition": {"field": "country_type", "operator": "eq", "value": "overseas"},
              "action": {"required": True}}]

    assert validate_required_with_rules(fields, {"country_type": "overseas"}, rules) is not None
    assert validate_required_with_rules(fields, {"country_type": "overseas", "country_name": "越南"}, rules) is None
    assert validate_required_with_rules(fields, {"country_type": "domestic"}, rules) is None


def test_hidden_field_never_reports_required():
    """防死锁：静态必填的字段被显隐规则藏起来时，后端不得再拦。"""
    fields = [F("country_type"), F("country_name", required=True)]
    rules = [vis_rule("r1", "country_name",
                      {"field": "country_type", "operator": "eq", "value": "overseas"})]

    # 国内 → country_name 被隐藏 → 不该报必填（此前后端会拦，前端却不显示该字段）
    assert validate_required_with_rules(fields, {"country_type": "domestic"}, rules) is None
    # 国外 → 字段可见 → 正常拦
    err = validate_required_with_rules(fields, {"country_type": "overseas"}, rules)
    assert err and "country_name" in err


def test_formula_and_auto_number_exempt_from_required():
    fields = [F("total", type="formula", required=True), F("no", type="auto_number", required=True)]
    assert validate_required_with_rules(fields, {}, []) is None


def test_role_permission_can_force_hidden_or_required():
    fields = [F("secret"), F("note")]
    st = compute_field_states(fields, {}, [], [{"fieldId": "secret", "access": "hidden"}])
    assert st["secret"]["visible"] is False
    assert validate_required_with_rules(
        fields, {}, [], [{"fieldId": "note", "access": "required"}]) is not None


# ===== 明细子表 =====

def test_detail_table_required_column():
    fields = [F("items", type="detail_table", label="产品",
                detail_table_columns=[{"id": "name", "label": "名称", "type": "text", "required": True}])]
    assert validate_required_with_rules(fields, {"items": [{"name": "泵"}]}, []) is None
    err = validate_required_with_rules(fields, {"items": [{"name": "泵"}, {"name": ""}]}, [])
    assert err and "第 2 行" in err


def test_detail_table_any_row_matches_condition():
    fields = [
        F("items", type="detail_table",
          detail_table_columns=[{"id": "qty", "label": "数量", "type": "number"}]),
        F("approval_note"),
    ]
    rules = [vis_rule("r1", "approval_note", {"field": "qty", "operator": "gt", "value": 100})]
    st = compute_field_states(fields, {"items": [{"qty": 5}, {"qty": 500}]}, rules)
    assert st["approval_note"]["visible"] is True, "任一行满足即命中"
    st = compute_field_states(fields, {"items": [{"qty": 5}, {"qty": 9}]}, rules)
    assert st["approval_note"]["visible"] is False
