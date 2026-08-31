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
    assert JDY_ROLE_TO_CRM_CODE["5f699f9a4f8b410006f2819f"] == "logistics_approval"
    assert JDY_ROLE_TO_CRM_CODE["5f69a16377e34d0006f13047"] == "ship_sales_outbound"
    assert JDY_ROLE_TO_CRM_CODE["66889a1cdc970f6d8b318231"] == "gate_guard"
    assert JDY_ROLE_TO_CRM_CODE["5f6c3e539a4cbe0006b74d65"] == "cs_office"
    assert JDY_ROLE_TO_CRM_CODE["5f6c3e74bb221e00067d4f39"] == "cs_delay_approve"
    assert JDY_ROLE_TO_CRM_CODE["5f69a45077e34d0006f136dd"] == "legal"
    assert JDY_ROLE_TO_CRM_CODE["5f55d129a526650006b36c22"] == "prod_material_code"
    assert JDY_ROLE_TO_CRM_CODE["5f55d115968dad000698ae27"] == "prod_elec_workshop"
    assert JDY_ROLE_TO_CRM_CODE["60fe45b98db9d500080ea397"] == "prod_elec_workshop"
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


def test_prod_elec_workshop_member_roster():
    from app.common.rbac_catalog import STANDARD_ROLES
    from app.common.rbac_sync import (
        PROD_ELEC_WORKSHOP_MEMBER_REAL_NAMES,
        PROD_ELEC_WORKSHOP_MEMBER_USERNAMES,
    )

    role = next(r for r in STANDARD_ROLES if r["code"] == "prod_elec_workshop")
    assert role["name"] == "1.2.8生产卡/补充流程-电气车间"
    assert (role.get("scope_by_resource") or {}).get("prod_card_supplement") == "all"
    assert set(PROD_ELEC_WORKSHOP_MEMBER_REAL_NAMES) == {"李同民", "张雨辰"}
    assert len(PROD_ELEC_WORKSHOP_MEMBER_USERNAMES) == 2


def test_prod_quality_control_role_catalog():
    from app.common.rbac_catalog import STANDARD_ROLES, role_perm_codes
    from app.common.rbac_sync import PROD_QUALITY_CONTROL_DEPT_NAMES

    role = next(r for r in STANDARD_ROLES if r["code"] == "prod_quality_control")
    assert role["name"] == "工艺与质量控制部"
    sbr = role.get("scope_by_resource") or {}
    assert sbr.get("prod_card_supplement") == "all"
    assert sbr.get("contract") == "all"
    perms = set(role_perm_codes(role))
    assert "form_data:view" in perms
    assert "form_data:edit" in perms
    assert "order:view" in perms
    assert "order:edit" in perms
    assert "product:view" in perms
    assert "product:edit" in perms
    assert "contract:view" in perms
    assert "approval:approve" not in perms
    assert "approval:decide" not in perms
    assert PROD_QUALITY_CONTROL_DEPT_NAMES == ("工艺与质量控制部",)


def test_plan_procurement_dept_role_catalog():
    from app.common.rbac_catalog import STANDARD_ROLES, role_perm_codes
    from app.common.rbac_sync import PLAN_PROCUREMENT_DEPT_NAMES

    role = next(r for r in STANDARD_ROLES if r["code"] == "plan_procurement_dept")
    assert role["name"] == "计划采购部"
    sbr = role.get("scope_by_resource") or {}
    assert sbr.get("prod_card_supplement") == "all"
    perms = set(role_perm_codes(role))
    assert "form_data:view" in perms
    assert "order:view" in perms
    assert "product:view" in perms
    assert "approval:approve" not in perms
    assert PLAN_PROCUREMENT_DEPT_NAMES == ("计划采购部",)


def test_plan_dispatch_dept_role_catalog():
    from app.common.rbac_catalog import STANDARD_ROLES, role_perm_codes
    from app.common.rbac_sync import PLAN_DISPATCH_DEPT_NAMES

    role = next(r for r in STANDARD_ROLES if r["code"] == "plan_dispatch_dept")
    assert role["name"] == "计划调度室"
    sbr = role.get("scope_by_resource") or {}
    assert sbr.get("contract") == "all"
    assert sbr.get("prod_card_supplement") == "all"
    perms = set(role_perm_codes(role))
    assert "form_data:view" in perms
    assert "contract:view" in perms
    assert "order:view" in perms
    assert "product:view" in perms
    assert "approval:approve" not in perms
    assert PLAN_DISPATCH_DEPT_NAMES == ("计划调度室",)


def test_contract_registration_dept_role_catalog():
    from app.common.rbac_catalog import STANDARD_ROLES, role_perm_codes
    from app.common.rbac_sync import CONTRACT_REGISTRATION_DEPT_NAMES

    role = next(r for r in STANDARD_ROLES if r["code"] == "contract_registration_dept")
    assert role["name"] == "合同登记（部门）"
    assert role["scope"] == "all"
    assert (role.get("scope_by_resource") or {}).get("contract") == "all"
    perms = set(role_perm_codes(role))
    assert "contract:view" in perms
    assert "contract:create" in perms
    assert "contract:edit" in perms
    assert "project:view" in perms
    assert "customer:view" in perms
    assert CONTRACT_REGISTRATION_DEPT_NAMES == ("财务部", "采购部", "行政中心")


def test_legal_member_roster():
    from app.common.rbac_catalog import STANDARD_ROLES
    from app.common.rbac_sync import LEGAL_MEMBER_REAL_NAMES, LEGAL_MEMBER_USERNAMES

    role = next(r for r in STANDARD_ROLES if r["code"] == "legal")
    assert role["name"] == "24.2.3合同/项目评审-法务审批多人"
    assert set(LEGAL_MEMBER_REAL_NAMES) == {"杜习慧", "孔雪", "张孟杰"}
    assert len(LEGAL_MEMBER_USERNAMES) == 3


def test_charger_rule_maps_new_roles():
    cases = [
        ("5f699f9a4f8b410006f2819f", "物流审批", "logistics_approval"),
        ("5f69a16377e34d0006f13047", "24.1发货通知流程-销售出库", "ship_sales_outbound"),
        ("66889a1cdc970f6d8b318231", "240706门岗保卫组", "gate_guard"),
        ("5f6c3e74bb221e00067d4f39", "7.5客户服务延期申请-客服审批", "cs_delay_approve"),
        ("5f69a45077e34d0006f136dd", "24.2.3合同/项目评审-法务审批多人", "legal"),
        ("5f55d129a526650006b36c22", "1.2.8生产卡/补充流程-物料编码", "prod_material_code"),
        ("5f55d115968dad000698ae27", "1.2.8生产卡/补充流程-电气车间", "prod_elec_workshop"),
        ("60fe45b98db9d500080ea397", "1.2.8生产卡/补充流程-电气编码", "prod_elec_workshop"),
    ]
    for rid, name, code in cases:
        rule = charger_rule({"roles": [{"_id": rid, "name": name}]}, {})
        assert rule["type"] == "specified_role", (rid, rule)
        assert rule["value"] == code, (rid, rule)


def test_logistics_approval_member_roster():
    from app.common.rbac_catalog import STANDARD_ROLES
    from app.common.rbac_sync import (
        LOGISTICS_APPROVAL_MEMBER_REAL_NAMES,
        LOGISTICS_APPROVAL_MEMBER_USERNAMES,
    )

    role = next(r for r in STANDARD_ROLES if r["code"] == "logistics_approval")
    assert role["name"] == "物流审批"
    assert (role.get("scope_by_resource") or {}).get("shipment_notice") == "all"
    assert set(LOGISTICS_APPROVAL_MEMBER_REAL_NAMES) == {
        "孔令山", "李娜", "马瑞草", "韩文祯", "张冠杰",
    }
    assert len(LOGISTICS_APPROVAL_MEMBER_USERNAMES) == 5


def test_apply_shipment_notice_roles_idempotent():
    nodes = [
        {"id": "n1", "name": "物流审批", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n8", "name": "仓库", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n10", "name": "仓库判定", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n27", "name": "抄送门岗", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
    ]
    assert _flow_shipment_logistics_needs_fix(nodes)
    assert apply_shipment_notice_approvers(nodes)
    assert nodes[0]["approver_rule"]["type"] == "specified_role"
    assert nodes[0]["approver_rule"]["value"] == "logistics_approval"
    assert nodes[0].get("multi_mode") == "or_sign"
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

    xnodes2 = [{
        "id": "n29", "name": "法务主管审批",
        "approver_rule": {"type": "specified_user", "value": "492105073721398323"},
    }]
    assert _flow_xunhan_contract_review_needs_approver_fix(xnodes2)
    assert apply_xunhan_contract_review_approvers(xnodes2)
    assert xnodes2[0]["approver_rule"]["value"] == "02364840011125"
    assert not apply_xunhan_contract_review_approvers(xnodes2)
    assert not _flow_xunhan_contract_review_needs_approver_fix(xnodes2)

    from app.domains.lowcode.workflow_service import (
        _XUNHAN_FEEDBACK_REENTER_EDGES,
        patch_xunhan_contract_review_feedback_routes,
        _flow_xunhan_feedback_routes_need_fix,
    )
    routes = [{"id": "r_6", "source": "n12", "target": "n1__2"}]
    assert _flow_xunhan_feedback_routes_need_fix(routes)
    assert patch_xunhan_contract_review_feedback_routes(routes)
    assert routes[0].get("reenter") is True
    routes2 = [
        {"id": f"r_{s}_{t}", "source": s, "target": t}
        for s, t in _XUNHAN_FEEDBACK_REENTER_EDGES
    ]
    assert patch_xunhan_contract_review_feedback_routes(routes2)
    assert all(r.get("reenter") for r in routes2)
    assert not _flow_xunhan_feedback_routes_need_fix(routes2)
    assert not patch_xunhan_contract_review_feedback_routes(routes2)

    pnodes = [
        {"id": "n5", "name": "物料编码", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n10", "name": "电气编码", "approver_rule": {"type": "specified_user", "value": ["02364337364933"]}},
        {"id": "n45", "name": "法务审核", "approver_rule": {"type": "specified_role", "value": "sales_manager"}},
        {"id": "n4", "name": "通知生产", "type": "approval", "approver_rule": {"type": "specified_user", "value": "02425350081942"}},
    ]
    assert _flow_prod_card_supplement_needs_approver_fix(pnodes)
    assert apply_prod_card_supplement_approvers(pnodes)
    assert pnodes[0]["approver_rule"]["value"] == "prod_material_code"
    assert not pnodes[0]["approver_rule"].get("exclude_initiator")
    assert pnodes[1]["approver_rule"]["value"] == "prod_elec_workshop"
    assert pnodes[2]["approver_rule"]["value"] == "legal"
    assert not apply_prod_card_supplement_approvers(pnodes)

    from app.domains.lowcode.workflow_service import (
        apply_prod_card_notify_production_cc,
        _flow_prod_card_notify_cc_needs_fix,
    )
    assert _flow_prod_card_notify_cc_needs_fix(pnodes)
    assert apply_prod_card_notify_production_cc(pnodes)
    assert set(pnodes[3]["cc_rule"]["value"]) == {
        "02364437547295", "02362247571234189", "1739424832704465",
    }
    assert not apply_prod_card_notify_production_cc(pnodes)
    assert not _flow_prod_card_notify_cc_needs_fix(pnodes)


def test_prod_card_material_allows_initiator():
    from app.domains.lowcode.workflow_service import (
        _flow_prod_card_material_excludes_initiator,
        apply_prod_card_material_allow_initiator,
    )
    nodes = [{
        "id": "n5",
        "name": "物料编码",
        "approver_rule": {
            "type": "specified_role",
            "value": "prod_material_code",
            "exclude_initiator": True,
        },
    }]
    assert _flow_prod_card_material_excludes_initiator(nodes)
    assert apply_prod_card_material_allow_initiator(nodes)
    assert not nodes[0]["approver_rule"].get("exclude_initiator")
    assert not _flow_prod_card_material_excludes_initiator(nodes)
    assert not apply_prod_card_material_allow_initiator(nodes)


def test_apply_correspondence_office_role():
    nodes = [
        {"id": "n3", "name": "内勤办理",
         "approver_rule": {"type": "specified_user", "value": ["0236446249514"]}},
    ]
    assert _flow_cs_correspondence_needs_approver_fix(nodes)
    assert apply_cs_correspondence_approvers(nodes)
    assert nodes[0]["approver_rule"]["value"] == "cs_office"
    assert not apply_cs_correspondence_approvers(nodes)
