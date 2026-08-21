# -*- coding: utf-8 -*-
"""九流程审批角色：charger 映射 + apply 幂等。"""
from app.domains.lowcode.pickable_scope import JDY_ROLE_TO_CRM_CODE
from scripts._gen_drawing_jdy import charger_rule
from app.domains.lowcode.workflow_service import (
    apply_shipment_notice_approvers,
    apply_cs_service_delay_approvers,
    apply_cs_correspondence_approvers,
    apply_xunhan_contract_review_approvers,
    apply_prod_card_supplement_approvers,
    _flow_shipment_logistics_needs_fix,
    _flow_cs_service_delay_needs_approver_fix,
    _flow_cs_correspondence_needs_approver_fix,
    _flow_xunhan_contract_review_needs_approver_fix,
    _flow_prod_card_supplement_needs_approver_fix,
)


def test_jdy_role_crm_code_mapping():
    assert JDY_ROLE_TO_CRM_CODE["5f69a16377e34d0006f13047"] == "ship_sales_outbound"
    assert JDY_ROLE_TO_CRM_CODE["66889a1cdc970f6d8b318231"] == "gate_guard"
    assert JDY_ROLE_TO_CRM_CODE["5f6c3e539a4cbe0006b74d65"] == "cs_office"
    assert JDY_ROLE_TO_CRM_CODE["5f6c3e74bb221e00067d4f39"] == "cs_delay_approve"
    assert JDY_ROLE_TO_CRM_CODE["5f69a45077e34d0006f136dd"] == "legal"
    assert JDY_ROLE_TO_CRM_CODE["5f55d129a526650006b36c22"] == "prod_material_code"
    assert JDY_ROLE_TO_CRM_CODE["5f69a976fbf7110006288375"] == "legal"
    assert JDY_ROLE_TO_CRM_CODE["63815e3a7fb607000acc9195"] == "room_leader"


def test_room_leader_member_roster():
    from app.common.rbac_catalog import STANDARD_ROLES
    from app.common.rbac_sync import ROOM_LEADER_MEMBER_REAL_NAMES, ROOM_LEADER_MEMBER_USERNAMES

    role = next(r for r in STANDARD_ROLES if r["code"] == "room_leader")
    assert role["name"] == "设计指派27.3~4/1.2.8/6.8/27.16/19.3"
    assert len(ROOM_LEADER_MEMBER_USERNAMES) == 9
    assert set(ROOM_LEADER_MEMBER_REAL_NAMES) == {
        "曹修国", "樊磊", "丰芊", "刘松潮", "李兴玉", "吕芹", "王东明", "周彦立", "赵小康",
    }


def test_charger_rule_maps_new_roles():
    cases = [
        ("5f69a16377e34d0006f13047", "24.1发货通知流程-销售出库", "ship_sales_outbound"),
        ("66889a1cdc970f6d8b318231", "240706门岗保卫组", "gate_guard"),
        ("5f6c3e74bb221e00067d4f39", "7.5客户服务延期申请-客服审批", "cs_delay_approve"),
        ("5f69a45077e34d0006f136dd", "24.2.3合同/项目评审-法务审批多人", "legal"),
        ("5f55d129a526650006b36c22", "1.2.8生产卡/补充流程-物料编码", "prod_material_code"),
    ]
    for rid, name, code in cases:
        rule = charger_rule({"roles": [{"_id": rid, "name": name}]}, {})
        assert rule["type"] == "specified_role", (rid, rule)
        assert rule["value"] == code, (rid, rule)


def test_apply_shipment_notice_roles_idempotent():
    nodes = [
        {"id": "n1", "name": "物流审批", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n8", "name": "仓库", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n10", "name": "仓库判定", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n27", "name": "抄送门岗", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
    ]
    assert _flow_shipment_logistics_needs_fix(nodes)
    assert apply_shipment_notice_approvers(nodes)
    assert nodes[0]["approver_rule"]["type"] == "specified_user"
    assert nodes[1]["approver_rule"]["value"] == "ship_sales_outbound"
    assert nodes[2]["approver_rule"]["value"] == "ship_sales_outbound"
    assert nodes[3]["approver_rule"]["value"] == "gate_guard"
    assert not apply_shipment_notice_approvers(nodes)
    assert not _flow_shipment_logistics_needs_fix(nodes)


def test_apply_cs_service_delay_roles_idempotent():
    nodes = [
        {"id": "n3", "name": "客服反馈", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n4", "name": "客服审批", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n7", "name": "客服备案", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
    ]
    assert _flow_cs_service_delay_needs_approver_fix(nodes)
    assert apply_cs_service_delay_approvers(nodes)
    assert nodes[0]["approver_rule"]["value"] == "cs_office"
    assert nodes[1]["approver_rule"]["value"] == "cs_delay_approve"
    assert nodes[2]["approver_rule"]["value"] == "cs_office"
    assert not apply_cs_service_delay_approvers(nodes)


def test_apply_xunhan_and_prod_card_roles():
    xnodes = [{"id": "n3", "name": "法务审批", "approver_rule": {"type": "specified_role", "value": "sales_manager"}}]
    assert _flow_xunhan_contract_review_needs_approver_fix(xnodes)
    assert apply_xunhan_contract_review_approvers(xnodes)
    assert xnodes[0]["approver_rule"]["value"] == "legal"
    assert not apply_xunhan_contract_review_approvers(xnodes)

    pnodes = [
        {"id": "n5", "name": "物料编码", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n45", "name": "法务审核", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n4", "name": "通知生产", "type": "approval", "approver_rule": {"type": "specified_user", "value": "02425350081942"}},
    ]
    assert _flow_prod_card_supplement_needs_approver_fix(pnodes)
    assert apply_prod_card_supplement_approvers(pnodes)
    assert pnodes[0]["approver_rule"]["value"] == "prod_material_code"
    assert pnodes[1]["approver_rule"]["value"] == "legal"
    assert not apply_prod_card_supplement_approvers(pnodes)

    from app.domains.lowcode.workflow_service import (
        apply_prod_card_notify_production_cc,
        _flow_prod_card_notify_cc_needs_fix,
    )
    assert _flow_prod_card_notify_cc_needs_fix(pnodes)
    assert apply_prod_card_notify_production_cc(pnodes)
    assert set(pnodes[2]["cc_rule"]["value"]) == {
        "02364437547295", "02362247571234189", "1739424832704465",
    }
    assert not apply_prod_card_notify_production_cc(pnodes)
    assert not _flow_prod_card_notify_cc_needs_fix(pnodes)


def test_apply_correspondence_office_role():
    nodes = [
        {"id": "n3", "name": "内勤办理",
         "approver_rule": {"type": "specified_user", "value": ["0236446249514"]}},
    ]
    assert _flow_cs_correspondence_needs_approver_fix(nodes)
    assert apply_cs_correspondence_approvers(nodes)
    assert nodes[0]["approver_rule"]["value"] == "cs_office"
    assert not apply_cs_correspondence_approvers(nodes)
