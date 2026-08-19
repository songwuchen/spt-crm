# -*- coding: utf-8 -*-
from scripts._gen_drawing_jdy import charger_rule, _route_is_jdy_always_parallel
from app.domains.lowcode.workflow_service import (
    apply_cs_product_replace_approvers,
    _flow_cs_product_replace_needs_approver_fix,
    _approver_rule_matches,
)
from app.domains.lowcode.pickable_scope import (
    JDY_ROLE_TO_SPECIFIED_USER,
    JDY_ROLE_TO_SPECIFIED_USERS,
)


def test_charger_rule_user_widgets_dept_head():
    slug = {"_widget_1577520412656": "sales_person"}
    rule = charger_rule({
        "deptManager": {
            "userWidgets": {"_widget_1577520412656": [0]},
        },
    }, slug)
    assert rule == {
        "type": "form_field_person_dept_head",
        "value": "sales_person",
        "exclude_initiator": True,
    }


def test_charger_rule_cs_register_specified_users():
    rule = charger_rule({
        "roles": [{
            "_id": "62e9bfe0527ea90008320fab",
            "name": "7.1.2售出产品更换（补发）流程-客服补登",
        }],
    }, {})
    assert rule["type"] == "specified_user"
    assert isinstance(rule["value"], list)
    assert len(rule["value"]) == 4
    assert "0236446249514" in rule["value"]


def test_charger_rule_chief_specified_user():
    rule = charger_rule({
        "roles": [{
            "_id": "5f6597c8e7889c0006f12831",
            "name": "7.1.1售后服务申请及反馈-总工审批",
        }],
    }, {})
    assert rule["type"] == "specified_user"
    assert rule["value"] == "02364335378133"


def test_cs_product_replace_approver_upgrade():
    nodes = [
        {"id": "n1", "type": "approval", "name": "业务经理审批",
         "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n4", "type": "approval", "name": "客服会签",
         "approver_rule": {"type": "pickable_scope", "value": "cs_replace_cs_register"}},
    ]
    assert _flow_cs_product_replace_needs_approver_fix(nodes)
    assert apply_cs_product_replace_approvers(nodes)
    assert nodes[0]["approver_rule"]["type"] == "form_field_person_dept_head"
    assert nodes[1]["approver_rule"]["type"] == "specified_user"
    assert isinstance(nodes[1]["approver_rule"]["value"], list)
    assert not _flow_cs_product_replace_needs_approver_fix(nodes)


def test_approver_rule_list_value_equal():
    a = {"type": "specified_user", "value": ["b", "a"]}
    b = {"type": "specified_user", "value": ["a", "b"]}
    assert _approver_rule_matches(a, b)


def test_jdy_cs_role_user_maps():
    assert JDY_ROLE_TO_SPECIFIED_USERS["62e9bfe0527ea90008320fab"]
    assert JDY_ROLE_TO_SPECIFIED_USER["5f6597c8e7889c0006f12831"] == "02364335378133"


def test_jdy_always_parallel_route_not_exclusive():
    """简道云 cond=[] 映射的 __always 边不应参与互斥组。"""
    assert _route_is_jdy_always_parallel(
        {"source": "n6", "target": "n8", "condition": {"field": "__always", "operator": "is_empty"}},
    )
    assert not _route_is_jdy_always_parallel(
        {"source": "n6", "target": "n20", "condition": {"field": "field_24", "operator": "in", "value": ["是"]}},
    )
