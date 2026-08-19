# -*- coding: utf-8 -*-
from app.domains.lowcode.pickable_scope import (
    JDY_ROLE_NAME_TO_SPECIFIED_USERS,
    JDY_ROLE_TO_SPECIFIED_USERS,
)
from app.domains.lowcode.workflow_service import (
    apply_cs_product_return_approvers,
    _flow_cs_product_return_needs_approver_fix,
    _cs_return_want_for_node,
)
from app.domains.lowcode._customer_service_jdy_generated import CUSTOMER_SERVICE_JDY


def test_jdy_cs_return_role_users():
    users = JDY_ROLE_TO_SPECIFIED_USERS["64f2a247187194000af416be"]
    assert len(users) == 4
    assert JDY_ROLE_NAME_TO_SPECIFIED_USERS["230902客服内勤"] == users


def test_cs_product_return_generated_has_no_role_approvers():
    for n in CUSTOMER_SERVICE_JDY["cs_product_return"]["flow_nodes"]:
        rule = n.get("approver_rule") or {}
        assert rule.get("type") not in ("specified_role", "pickable_scope"), n.get("name")


def test_cs_product_return_approver_upgrade():
    nodes = [
        {"id": "n3", "type": "approval", "name": "客服办理/会签",
         "approver_rule": {"type": "specified_role", "value": "service_manager"}},
        {"id": "n20", "type": "approval", "name": "客服办理/会签",
         "approver_rule": {"type": "pickable_scope", "value": "cs_register"}},
        {"id": "n2__1", "type": "approval", "name": "仓库接收1",
         "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n29", "type": "approval", "name": "相关业务员",
         "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
    ]
    assert _flow_cs_product_return_needs_approver_fix(nodes)
    assert apply_cs_product_return_approvers(nodes)
    assert nodes[0]["approver_rule"]["type"] == "specified_user"
    assert isinstance(nodes[0]["approver_rule"]["value"], list)
    assert nodes[1]["approver_rule"]["type"] == "specified_user"
    assert nodes[2]["approver_rule"] == _cs_return_want_for_node(nodes[2])
    assert nodes[3]["approver_rule"]["type"] == "form_field_person"
    assert nodes[3]["approver_rule"]["value"] == "field_27"
    assert not _flow_cs_product_return_needs_approver_fix(nodes)


def test_cs_return_cs_users_match_replace_cs_register():
    """230902客服内勤 与 售出产品更换客服补登 为同一批人。"""
    replace = JDY_ROLE_TO_SPECIFIED_USERS["62e9bfe0527ea90008320fab"]
    ret = JDY_ROLE_TO_SPECIFIED_USERS["64f2a247187194000af416be"]
    assert sorted(replace) == sorted(ret)
