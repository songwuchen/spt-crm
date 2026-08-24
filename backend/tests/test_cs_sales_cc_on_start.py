# -*- coding: utf-8 -*-
from app.domains.lowcode.workflow_service import (
    _CS_SALES_CC_ON_START,
    _flow_missing_cs_sales_cc_on_start,
    apply_cs_sales_cc_on_start,
)


def _minimal_cs_flow():
    nodes = [
        {"id": "start", "type": "start", "name": "发起"},
        {"id": "n1", "type": "approval", "name": "业务经理"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes = [
        {"id": "r1", "source": "start", "target": "n1"},
        {"id": "r2", "source": "n1", "target": "end"},
    ]
    return nodes, routes


def test_apply_cs_sales_cc_on_start_idempotent():
    nodes, routes = _minimal_cs_flow()
    assert _flow_missing_cs_sales_cc_on_start(nodes, routes) is True
    assert apply_cs_sales_cc_on_start(nodes, routes) is True
    assert _flow_missing_cs_sales_cc_on_start(nodes, routes) is False
    assert apply_cs_sales_cc_on_start(nodes, routes) is False
    cc = next(n for n in nodes if n.get("id") == _CS_SALES_CC_ON_START)
    assert cc["type"] == "cc"
    assert cc["name"] == "抄送业务员"
    assert cc["approver_rule"] == {
        "type": "form_field_person",
        "value": "sales_person",
    }
    assert any(
        r.get("source") == "start"
        and r.get("target") == _CS_SALES_CC_ON_START
        and r.get("always") is True
        for r in routes
    )


def test_apply_cs_sales_cc_on_start_fixes_partial():
    nodes, routes = _minimal_cs_flow()
    nodes.append({
        "id": _CS_SALES_CC_ON_START,
        "type": "cc",
        "name": "抄送业务员",
        "approver_rule": {"type": "creator"},
    })
    assert _flow_missing_cs_sales_cc_on_start(nodes, routes) is True
    assert apply_cs_sales_cc_on_start(nodes, routes) is True
    cc = next(n for n in nodes if n.get("id") == _CS_SALES_CC_ON_START)
    assert cc["approver_rule"]["type"] == "form_field_person"
    assert _flow_missing_cs_sales_cc_on_start(nodes, routes) is False
