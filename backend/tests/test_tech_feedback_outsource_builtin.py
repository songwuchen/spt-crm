"""Builtin templates: 技术协议反馈单 + 合同外购件提前安排流程."""
from app.domains.lowcode.builtin_templates import get_builtin, list_builtin
from app.domains.lowcode.contract_outsource_early_fields import apply_contract_outsource_early_fields
from app.domains.lowcode.workflow_service import (
    _contract_outsource_designer_equipment_perms_aligned,
    _flow_is_jdy_contract_outsource_early,
    _flow_is_jdy_tech_agreement_feedback,
    _flow_outsource_biz_mgr_needs_dept_head,
    apply_contract_outsource_biz_dept_head,
    apply_contract_outsource_designer_equipment_perms,
)


def test_builtin_templates_include_tech_feedback_outsource_keys():
    keys = {t["key"] for t in list_builtin()}
    assert "tech_agreement_feedback" in keys
    assert "contract_outsource_early" in keys


def test_tech_agreement_feedback_builtin_pack():
    bt = get_builtin("tech_agreement_feedback")
    assert bt is not None
    assert bt["category"] == "研究院"
    fields = bt.get("field_definitions") or []
    assert any(f.get("id") == "serial_no" for f in fields)
    assert any(f.get("id") == "contract_no" and f.get("type") == "contract" for f in fields)
    from app.domains.lowcode._tech_feedback_outsource_generated import TECH_FEEDBACK_OUTSOURCE_JDY
    pack = TECH_FEEDBACK_OUTSOURCE_JDY["tech_agreement_feedback"]
    nodes = pack.get("flow_nodes") or []
    routes = pack.get("flow_routes") or []
    assert _flow_is_jdy_tech_agreement_feedback(nodes, routes)
    assert len([n for n in nodes if n.get("type") == "approval"]) >= 8


def test_contract_outsource_early_builtin_pack():
    bt = get_builtin("contract_outsource_early")
    assert bt is not None
    assert bt["category"] == "合同"
    fields = bt.get("field_definitions") or []
    link = next(f for f in fields if f.get("id") == "link_prod_card")
    assert link.get("type") == "select_data"
    assert (link.get("props") or {}).get("source_form_code") == "prod_card_supplement"
    detail = next(f for f in fields if f.get("id") == "equipment_details")
    cols = detail.get("detail_table_columns") or []
    assert len(cols) >= 8
    assert detail.get("available_on_create") is False
    assert detail.get("fill_stage") == "approver"
    designer_col = next(c for c in cols if c.get("id") == "designer")
    assert designer_col.get("available_on_create") is False
    assert designer_col.get("fill_stage") == "approver"
    from app.domains.lowcode._tech_feedback_outsource_generated import TECH_FEEDBACK_OUTSOURCE_JDY
    pack = TECH_FEEDBACK_OUTSOURCE_JDY["contract_outsource_early"]
    nodes = pack.get("flow_nodes") or []
    assert _flow_is_jdy_contract_outsource_early(nodes)


def test_contract_outsource_biz_mgr_upgrades_to_dept_head():
    nodes = [{
        "id": "aphpkw2", "type": "approval", "name": "业务部门经理",
        "approver_rule": {"type": "direct_supervisor"},
    }]
    assert _flow_outsource_biz_mgr_needs_dept_head(nodes)
    assert apply_contract_outsource_biz_dept_head(nodes)
    assert nodes[0]["approver_rule"] == {"type": "dept_head", "exclude_initiator": True}
    assert not _flow_outsource_biz_mgr_needs_dept_head(nodes)


def test_contract_outsource_equipment_details_not_on_create():
    defs = [{
        "id": "equipment_details",
        "type": "detail_table",
        "label": "设备明细",
        "required": True,
        "available_on_create": True,
        "fill_stage": "initiator",
        "detail_table_columns": [
            {"id": "designer", "type": "person", "label": "设计员"},
            {"id": "product_name", "type": "text", "label": "产品名称"},
        ],
    }]
    apply_contract_outsource_early_fields(defs)
    detail = defs[0]
    assert detail["available_on_create"] is False
    assert detail["fill_stage"] == "approver"
    assert next(c for c in detail["detail_table_columns"] if c["id"] == "designer")["fill_stage"] == "approver"


def test_contract_outsource_designer_node_can_edit_equipment_details():
    nodes = [{
        "id": "n_designer", "type": "approval", "name": "设计员",
        "field_perms": [{"field": "designer_single", "access": "editable"}],
    }]
    assert not _contract_outsource_designer_equipment_perms_aligned(nodes)
    assert apply_contract_outsource_designer_equipment_perms(nodes)
    perms = {p["field"]: p["access"] for p in nodes[0]["field_perms"]}
    assert perms["equipment_details"] == "editable"
    assert not apply_contract_outsource_designer_equipment_perms(nodes)


def test_contract_outsource_dept_head_node_can_edit_equipment_details():
    nodes = [{
        "id": "apvm1ye", "type": "approval", "name": "科室主任",
        "field_perms": [{"field": "designer_multi", "access": "required"}],
    }]
    assert not _contract_outsource_designer_equipment_perms_aligned(nodes)
    assert apply_contract_outsource_designer_equipment_perms(nodes)
    perms = {p["field"]: p["access"] for p in nodes[0]["field_perms"]}
    assert perms["equipment_details"] == "editable"
    assert perms["designer_multi"] == "required"
