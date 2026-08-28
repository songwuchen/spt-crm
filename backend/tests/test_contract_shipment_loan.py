# -*- coding: utf-8 -*-
from app.domains.lowcode.workflow_service import _drawing_flow_graph


def test_contract_shipment_loan_flow_graph():
    graph = _drawing_flow_graph("contract_shipment_loan")
    assert graph is not None
    nodes, routes = graph
    assert len(nodes) >= 10
    assert len(routes) >= 10
    names = {n.get("name") for n in nodes}
    assert "经理审批" in names
    assert "发货借据" in names or "合同借据" in names


def test_contract_shipment_loan_fields():
    from app.domains.lowcode._contract_shipment_loan_jdy_generated import (
        CONTRACT_SHIPMENT_LOAN_JDY,
    )

    pack = CONTRACT_SHIPMENT_LOAN_JDY["contract_shipment_loan"]
    fields = pack["field_definitions"]
    assert len(fields) >= 20
    loan_type = next(f for f in fields if f["id"] == "field_3")
    assert loan_type["label"] == "借据类型"
    assert any(o["value"] == "合同借据" for o in loan_type["options"])
    assert any(o["value"] == "排产借据" for o in loan_type["options"])
    contract_pick = next(f for f in fields if f.get("jdy_widget") == "_widget_1756342534747")
    assert contract_pick["type"] == "contract"
    assert (contract_pick.get("props") or {}).get("contract_fill") == "contract_shipment_loan"


def test_contract_shipment_loan_required_and_rules():
    from app.domains.lowcode._contract_shipment_loan_jdy_generated import (
        CONTRACT_SHIPMENT_LOAN_JDY,
    )

    pack = CONTRACT_SHIPMENT_LOAN_JDY["contract_shipment_loan"]
    fields = pack["field_definitions"]
    n_req = sum(1 for f in fields if f.get("required"))
    n_col_req = sum(
        1 for f in fields for c in (f.get("detail_table_columns") or []) if c.get("required")
    )
    assert n_req >= 9, f"expected initiator required fields, got {n_req}"
    assert n_col_req >= 4, f"expected detail required columns, got {n_col_req}"
    field_15 = next(f for f in fields if f["id"] == "field_15")
    assert not field_15.get("required"), "field_15 发起不应必填"
    field_23 = next((f for f in fields if f["id"] == "field_23"), None)
    assert field_23 is not None, "应有审批节点 field_23"
    assert field_23.get("available_on_create") is False
    rules = pack.get("rule_definitions") or []
    assert len(rules) >= 3
    vis = [r for r in rules if r.get("type") == "visibility"]
    assert any(r.get("target_field_id") == "field_15" for r in vis)
    assert not any(
        r.get("type") == "required" and r.get("target_field_id") == "field_15"
        for r in rules
    )


def test_build_loan_fill_from_contract():
    from app.domains.lowcode.contract_shipment_loan_fields import (
        build_loan_fill_from_contract,
        map_contract_lines_to_loan_detail,
    )

    lines = map_contract_lines_to_loan_detail([
        {"name": "泵A", "spec": "X1", "qty": 2, "unit": "台", "unit_price": 100},
    ])
    assert len(lines) == 1
    assert lines[0]["field_8"] == "泵A"
    assert lines[0]["field_12"] == 200

    fill = build_loan_fill_from_contract(
        contract_id="c1",
        contract_no="HT001",
        drawing_no="TZ001",
        assignee_id="u1",
        department_id="d1",
        customer_id="cust1",
        key_clauses_json=[{"name": "泵B", "qty": 1, "unit_price": 50}],
        registration_json={"order_date": "2026-01-15"},
    )
    assert fill["contract_no"] == "c1"
    assert fill["customer_name"] == "cust1"
    assert fill["field_6"] == "d1"
    assert fill["field_2"] == "2026-01-15"
    assert fill["field_13"] == 50
