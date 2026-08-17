# -*- coding: utf-8 -*-
from app.domains.lowcode.workflow_service import (
    apply_quote_named_role_approvers,
    _flow_quote_needs_named_role_approvers,
)
from app.domains.lowcode.pickable_scope import (
    JDY_ROLE_TO_SPECIFIED_USER,
    JDY_ROLE_TO_SCOPE_CODE,
)


def test_quote_named_role_approvers_upgrade():
    nodes = [
        {"id": "n10", "type": "approval", "name": "王玲玲审批",
         "approver_rule": {"type": "specified_role", "value": "sales_manager", "jdy_role_hint": "王玲玲"}},
        {"id": "n11", "type": "approval", "name": "经理审批",
         "approver_rule": {"type": "specified_role", "value": "sales_manager", "jdy_role_hint": "热能利用-段荣凯"}},
        {"id": "n14", "type": "approval", "name": "冶金装备销售事业部",
         "approver_rule": {"type": "specified_role", "value": "sales_manager", "jdy_role_hint": "27.7核价管理流程-冶金"}},
        {"id": "n2", "type": "approval", "name": "财务核价",
         "approver_rule": {"type": "specified_user", "value": "0433406811775721"}},
    ]
    assert _flow_quote_needs_named_role_approvers(nodes)
    assert apply_quote_named_role_approvers(nodes)
    assert nodes[0]["approver_rule"]["type"] == "specified_user"
    assert nodes[0]["approver_rule"]["value"] == "01000533004677"
    assert nodes[1]["approver_rule"]["value"] == "02364714147257"
    assert nodes[2]["approver_rule"] == {
        "type": "pickable_scope", "value": "quote_metallurgy",
        "exclude_initiator": True, "jdy_role_hint": "27.7核价管理流程-冶金",
    }
    assert not _flow_quote_needs_named_role_approvers(nodes)
    assert not apply_quote_named_role_approvers(nodes)


def test_jdy_role_maps_cover_quote():
    assert JDY_ROLE_TO_SPECIFIED_USER["5f65673064514d0006b13a66"] == "01000533004677"
    assert JDY_ROLE_TO_SPECIFIED_USER["5f46003a5c11340006b167f2"] == "02364714147257"
    assert JDY_ROLE_TO_SCOPE_CODE["5f6c394b2ad3770006ded49a"] == "quote_metallurgy"
