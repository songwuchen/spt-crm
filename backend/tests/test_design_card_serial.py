"""新设计卡号 / 方案流水号规则 / 部门名归一。"""
from app.domains.lowcode.dept_code import (
    DESIGN_CARD_SERIAL_RULES,
    SCHEME_SERIAL_NO_RULES,
    apply_design_card_serial_rules,
    apply_scheme_serial_no_field,
    normalize_dept_name,
)
from app.domains.lowcode.serial_number import (
    _resolve_digits,
    _resolve_reset_period,
    normalize_serial_rules,
)


def test_normalize_dept_name_parens():
    assert normalize_dept_name("(暂存）F事业部") == "（暂存）F事业部"
    assert normalize_dept_name(" 精品砂石事业部 ") == "精品砂石事业部"


def test_design_card_serial_rules_shape():
    types = [r["type"] for r in DESIGN_CARD_SERIAL_RULES]
    assert types == ["field", "text", "date", "counter"]
    assert DESIGN_CARD_SERIAL_RULES[0]["field_id"] == "dept_code"
    assert DESIGN_CARD_SERIAL_RULES[1]["value"] == "-"
    assert DESIGN_CARD_SERIAL_RULES[2]["format"] == "yyyyMMdd"
    assert DESIGN_CARD_SERIAL_RULES[2]["date_field"] == "apply_datetime"
    counter = DESIGN_CARD_SERIAL_RULES[3]
    assert counter["digits"] == 2
    assert counter["reset_period"] == "daily"
    assert counter["period_scope_field"] == "dept_code"


def test_apply_design_card_serial_rules_mutates_field():
    fields = [
        {"id": "dept_code", "type": "text", "label": "部门编号"},
        {"id": "design_card_no", "type": "text", "label": "新设计卡号"},
    ]
    apply_design_card_serial_rules(fields)
    fd = fields[1]
    assert fd["type"] == "auto_number"
    rules = normalize_serial_rules(fd.get("props"))
    assert any(r.get("type") == "counter" for r in rules)
    assert any(r.get("field_id") == "dept_code" for r in rules if r.get("type") == "field")


def test_scheme_serial_no_rules_branch_by_type():
    assert SCHEME_SERIAL_NO_RULES[0]["type"] == "date"
    counter = SCHEME_SERIAL_NO_RULES[1]
    assert counter["type"] == "counter"
    assert counter["period_scope_field"] == "scheme_type"
    fields = [{"id": "scheme_type", "type": "radio", "options": [
        {"label": "领用", "value": "requisition"},
        {"label": "安装图", "value": "install"},
    ]}]
    assert _resolve_digits(counter, {"scheme_type": "requisition"}, fields) == 2
    assert _resolve_digits(counter, {"scheme_type": "install"}, fields) == 4
    assert _resolve_reset_period(counter, {"scheme_type": "requisition"}, fields) == "daily"
    assert _resolve_reset_period(counter, {"scheme_type": "install"}, fields) == "none"


def test_apply_scheme_serial_no_field_inserts():
    fields = [
        {"id": "scheme_type", "type": "radio", "label": "方案类型"},
        {"id": "apply_datetime", "type": "date", "label": "日期时间"},
    ]
    apply_scheme_serial_no_field(fields)
    assert fields[1]["id"] == "serial_no"
    assert fields[1]["type"] == "auto_number"
    rules = normalize_serial_rules(fields[1].get("props"))
    assert any(r.get("type") == "counter" for r in rules)
