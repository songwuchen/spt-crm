# -*- coding: utf-8 -*-
from app.domains.lowcode.formula_engine import compute_formula_fields
from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_contract_pick_fields


def test_order_type_merged_formula_non_supplement():
    defs = [
        {
            "id": "field",
            "type": "formula",
            "props": {"formula": "IF($is_supplement#=='是','补充',$order_type#)"},
        },
    ]
    data = compute_formula_fields(
        {"is_supplement": "否", "order_type": "备件"},
        defs,
        "",
    )
    assert data["field"] == "备件"


def test_order_type_merged_formula_supplement():
    defs = [
        {
            "id": "field",
            "type": "formula",
            "props": {"formula": "IF($is_supplement#=='是','补充',$order_type#)"},
        },
    ]
    data = compute_formula_fields(
        {"is_supplement": "是", "order_type": "设备"},
        defs,
        "",
    )
    assert data["field"] == "补充"


def test_string_eq_not_coerced_via_zero():
    """非数字字符串不可经 _to_num 变成 0 后误判相等。"""
    defs = [
        {
            "id": "out",
            "type": "formula",
            "props": {"formula": "IF($a#=='是','Y','N')"},
        },
    ]
    assert compute_formula_fields({"a": "否"}, defs, "")["out"] == "N"
    assert compute_formula_fields({"a": "是"}, defs, "")["out"] == "Y"


def test_apply_prod_card_sets_merged_formula():
    defs = [
        {"id": "field", "type": "text", "label": "下单类型（合并含补充）"},
        {"id": "order_type", "type": "radio", "label": "下单类型"},
    ]
    apply_prod_card_contract_pick_fields(defs)
    f = next(x for x in defs if x.get("id") == "field")
    assert f["type"] == "formula"
    assert f["props"]["formula"] == "IF($is_supplement#=='是','补充',$order_type#)"
