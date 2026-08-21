# -*- coding: utf-8 -*-
from app.domains.lowcode.payment_registration_fields import apply_payment_registration_fields
from app.domains.lowcode.formula_engine import compute_formula_fields


def test_apply_payment_registration_fields():
    defs = [
        {"id": "payment_no", "type": "text", "label": "收款号"},
        {"id": "payment_date", "type": "datetime", "label": "来款日期", "required": True},
        {"id": "customer_name", "type": "text", "label": "单位名称"},
        {"id": "payment_total", "type": "number", "label": "来款合计", "available_on_create": True},
        {"id": "sales_person", "type": "person", "label": "业务人员", "available_on_create": True},
        {"id": "payment_allocation", "type": "detail_table", "label": "款项分配"},
        {"id": "alloc_total", "type": "number", "label": "分配金额合计"},
        {"id": "remark_2", "type": "textarea", "label": "备注"},
    ]
    apply_payment_registration_fields(defs)
    assert defs[0]["type"] == "auto_number"
    assert defs[0]["form_editable"] is False
    assert defs[0]["props"]["serial_rules"][0]["value"] == "SKDJ-"
    assert defs[1]["type"] == "date"
    assert defs[1]["props"]["date_only"] is True
    assert defs[1]["props"]["show_time"] is False
    assert defs[2]["type"] == "customer"
    assert defs[3]["type"] == "formula"
    assert defs[3]["props"]["formula"] == "SUM($payment_details.amount#)"
    assert defs[4]["available_on_create"] is False
    assert defs[4]["fill_stage"] == "approver"
    assert defs[5]["available_on_create"] is False
    assert defs[6]["type"] == "formula"
    assert defs[6]["available_on_create"] is False
    assert defs[7]["available_on_create"] is False


def test_payment_total_formula_sums_details():
    defs = [
        {
            "id": "payment_details",
            "type": "detail_table",
            "detail_table_columns": [{"id": "amount", "type": "number"}],
        },
        {
            "id": "payment_total",
            "type": "formula",
            "props": {"formula": "SUM($payment_details.amount#)"},
        },
    ]
    data = compute_formula_fields(
        {"payment_details": [{"amount": 10}, {"amount": 25.5}]},
        defs,
        "",
    )
    assert float(data["payment_total"]) == 35.5
