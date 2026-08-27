# -*- coding: utf-8 -*-
from app.domains.lowcode.formula_engine import evaluate_submit_validations
from app.domains.lowcode.payment_registration_fields import (
    PAYMENT_ALLOC_TOTAL_SUBMIT_RULES,
    apply_payment_registration_fields,
    apply_payment_registration_submit_validations,
    flow_payment_needs_submit_validations,
)
from app.domains.lowcode.wf_submit_validation import (
    assert_node_submit_validations,
    parse_submit_validations,
)


def _payment_field_defs():
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
        {
            "id": "payment_allocation",
            "type": "detail_table",
            "detail_table_columns": [{"id": "alloc_amount", "type": "number"}],
        },
        {
            "id": "alloc_total",
            "type": "formula",
            "props": {"formula": "SUM($payment_allocation.alloc_amount#)"},
        },
    ]
    apply_payment_registration_fields(defs)
    return defs


def test_apply_payment_registration_submit_validations():
    nodes = [
        {"id": "n1", "type": "approval", "name": "内勤处理"},
        {"id": "n2", "type": "approval", "name": "采购"},
    ]
    assert apply_payment_registration_submit_validations(nodes)
    assert nodes[0]["submit_validations"] == PAYMENT_ALLOC_TOTAL_SUBMIT_RULES
    assert "submit_validations" not in nodes[1]
    assert not apply_payment_registration_submit_validations(nodes)


def test_flow_payment_needs_submit_validations():
    nodes = [{"id": "n1", "type": "approval", "name": "内勤处理"}]
    assert flow_payment_needs_submit_validations(nodes)
    apply_payment_registration_submit_validations(nodes)
    assert not flow_payment_needs_submit_validations(nodes)


def test_evaluate_submit_validations_payment_alloc_total():
    defs = _payment_field_defs()
    rules = PAYMENT_ALLOC_TOTAL_SUBMIT_RULES
    ok_data = {
        "payment_details": [{"amount": 100}, {"amount": 50}],
        "payment_allocation": [{"alloc_amount": 80}, {"alloc_amount": 70}],
    }
    assert evaluate_submit_validations(ok_data, defs, rules) is None

    bad_data = {
        "payment_details": [{"amount": 100}],
        "payment_allocation": [{"alloc_amount": 90}],
    }
    msg = evaluate_submit_validations(bad_data, defs, rules)
    assert msg == PAYMENT_ALLOC_TOTAL_SUBMIT_RULES[0]["message"]


def test_assert_node_submit_validations_blocks_mismatch():
    defs = _payment_field_defs()
    node = {"submit_validations": PAYMENT_ALLOC_TOTAL_SUBMIT_RULES}
    form_data = {
        "payment_details": [{"amount": 200}],
        "payment_allocation": [{"alloc_amount": 100}],
    }
    try:
        assert_node_submit_validations(
            node,
            form_data=form_data,
            field_updates={"payment_allocation": [{"alloc_amount": 100}]},
            form_fields=defs,
            action="approve",
        )
        assert False, "expected validation error"
    except Exception as e:
        assert "来款合计" in str(getattr(e, "message", e))

    assert_node_submit_validations(
        node,
        form_data=form_data,
        field_updates={"payment_allocation": [{"alloc_amount": 200}]},
        form_fields=defs,
        action="approve",
    )


def test_assert_node_submit_validations_skips_save():
    defs = _payment_field_defs()
    node = {"submit_validations": PAYMENT_ALLOC_TOTAL_SUBMIT_RULES}
    assert_node_submit_validations(
        node,
        form_data={"payment_details": [{"amount": 100}]},
        field_updates={"payment_allocation": [{"alloc_amount": 50}]},
        form_fields=defs,
        action="save",
    )


def test_parse_submit_validations_accepts_remind():
    rules = parse_submit_validations({
        "submit_validations": [{"formula": "$a#==1", "remind": "提示"}],
    })
    assert rules == [{"formula": "$a#==1", "message": "提示"}]
