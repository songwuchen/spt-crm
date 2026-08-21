# -*- coding: utf-8 -*-
import pytest

from scripts._gen_drawing_jdy import charger_rule, _route_is_jdy_always_parallel
from app.domains.lowcode._customer_service_jdy_generated import CUSTOMER_SERVICE_JDY
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


def test_charger_rule_cs_register_maps_to_cs_office_role():
    """客服补登 JDY 角色 → CRM 指定角色 cs_office（成员在角色管理维护）。"""
    rule = charger_rule({
        "roles": [{
            "_id": "62e9bfe0527ea90008320fab",
            "name": "7.1.2售出产品更换（补发）流程-客服补登",
        }],
    }, {})
    assert rule["type"] == "specified_role"
    assert rule["value"] == "cs_office"
    assert rule.get("jdy_role_hint") == "7.1.2售出产品更换（补发）流程-客服补登"


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
    assert nodes[1]["approver_rule"]["type"] == "specified_role"
    assert nodes[1]["approver_rule"]["value"] == "cs_office"
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


def test_cs_product_replace_fault_class_not_at_create():
    """换货明细「故障分类」对齐简道云：发起不可填，客服补登填写。"""
    f12 = next(
        f for f in CUSTOMER_SERVICE_JDY["cs_product_replace"]["field_definitions"]
        if f["id"] == "field_12"
    )
    col = next(c for c in f12["detail_table_columns"] if c["id"] == "field_19")
    assert col["available_on_create"] is False
    assert col["fill_stage"] == "approver"
    assert col["required"] is True
    # 发起列仍必填
    col18 = next(c for c in f12["detail_table_columns"] if c["id"] == "field_18")
    assert col18.get("fill_stage") != "approver"


def test_cs_product_replace_create_skips_fault_class_required():
    """发起提交：明细有行但未填故障分类时不应拦截。"""
    from app.domains.lowcode.rule_engine import validate_required_with_rules

    fields = CUSTOMER_SERVICE_JDY["cs_product_replace"]["field_definitions"]
    values = {
        "field": "dept-1",
        "sales_person": "u1",
        "customer_name": "cust-1",
        "field_3": "addr",
        "field_4": "contact",
        "field_5": "否",
        "field_6": "是",
        "field_24": "否",
        "field_12": [{
            "contract_no": "c1",
            "field_13": "设备",
            "field_14": "型号",
            "field_15": 1,
            "field_16": "台",
            "field_17": "2025-11-20",
            "field_18": "说明",
        }],
    }
    assert validate_required_with_rules(fields, values) is None


def test_cs_product_replace_cs_register_requires_fault_class():
    """客服补登通过：换货明细每行须填故障分类。"""
    from app.common.exceptions import BusinessException
    from app.domains.lowcode.wf_field_writeback import validate_field_updates

    fields = CUSTOMER_SERVICE_JDY["cs_product_replace"]["field_definitions"]
    perms = [{"field": "field_12", "access": "editable"}]
    form_data = {"field_12": [{"field_18": "说明"}]}
    with pytest.raises(BusinessException):
        validate_field_updates(
            perms,
            {"field_12": form_data["field_12"]},
            action="approve",
            form_fields=fields,
            form_data=form_data,
        )
