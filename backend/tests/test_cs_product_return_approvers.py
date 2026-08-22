# -*- coding: utf-8 -*-
from app.domains.lowcode.pickable_scope import (
    JDY_ROLE_NAME_TO_SPECIFIED_USERS,
    JDY_ROLE_TO_SPECIFIED_USERS,
)
from app.domains.lowcode.workflow_service import (
    apply_cs_product_return_approvers,
    apply_cs_product_return_logistics_field_perms,
    _flow_cs_product_return_needs_approver_fix,
    _flow_cs_product_return_needs_logistics_field_fix,
    _cs_return_want_for_node,
)
from app.domains.lowcode._customer_service_jdy_generated import CUSTOMER_SERVICE_JDY


def test_jdy_cs_return_role_users():
    users = JDY_ROLE_TO_SPECIFIED_USERS["64f2a247187194000af416be"]
    assert len(users) == 4
    assert JDY_ROLE_NAME_TO_SPECIFIED_USERS["230902客服内勤"] == users


def test_cs_product_return_generated_cs_office_role():
    """客服办理节点应为 cs_office，其它节点不用空角色。"""
    for n in CUSTOMER_SERVICE_JDY["cs_product_return"]["flow_nodes"]:
        rule = n.get("approver_rule") or {}
        if n.get("id") in ("n3", "n20"):
            assert rule.get("type") == "specified_role"
            assert rule.get("value") == "cs_office"
            continue
        assert rule.get("type") not in ("pickable_scope",), n.get("name")
        if rule.get("type") == "specified_role":
            assert rule.get("value") != "sales_manager", n.get("name")


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
    assert nodes[0]["approver_rule"]["type"] == "specified_role"
    assert nodes[0]["approver_rule"]["value"] == "cs_office"
    assert nodes[1]["approver_rule"]["type"] == "specified_role"
    assert nodes[1]["approver_rule"]["value"] == "cs_office"
    assert nodes[2]["approver_rule"] == _cs_return_want_for_node(nodes[2])
    assert nodes[3]["approver_rule"]["type"] == "form_field_person"
    assert nodes[3]["approver_rule"]["value"] == "field_27"
    assert not _flow_cs_product_return_needs_approver_fix(nodes)


def test_cs_return_cs_users_match_replace_cs_register():
    """230902客服内勤 与 售出产品更换客服补登 为同一批人。"""
    replace = JDY_ROLE_TO_SPECIFIED_USERS["62e9bfe0527ea90008320fab"]
    ret = JDY_ROLE_TO_SPECIFIED_USERS["64f2a247187194000af416be"]
    assert sorted(replace) == sorted(ret)


def test_cs_product_return_logistics_drops_detail_perm():
    """物流中心本节点可填区不含退回明细（避免误卡仓库判定）。"""
    n17 = next(
        n for n in CUSTOMER_SERVICE_JDY["cs_product_return"]["flow_nodes"]
        if n.get("id") == "n17"
    )
    assert all(p.get("field") != "field_7" for p in (n17.get("field_perms") or []))
    assert any(p.get("field") == "field_25" for p in (n17.get("field_perms") or []))

    nodes = [{
        "id": "n17", "type": "approval", "name": "物流中心",
        "field_perms": [
            {"field": "field_7", "access": "editable"},
            {"field": "field_25", "access": "required"},
        ],
    }]
    assert _flow_cs_product_return_needs_logistics_field_fix(nodes)
    assert apply_cs_product_return_logistics_field_perms(nodes)
    assert nodes[0]["field_perms"] == [{"field": "field_25", "access": "required"}]
    assert not _flow_cs_product_return_needs_logistics_field_fix(nodes)
