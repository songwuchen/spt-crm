"""Builtin templates: 技术协议反馈单 + 合同外购件提前安排流程."""
from app.domains.lowcode.builtin_templates import get_builtin, list_builtin
from app.domains.lowcode.workflow_service import (
    _flow_is_jdy_contract_outsource_early,
    _flow_is_jdy_tech_agreement_feedback,
    _flow_outsource_biz_mgr_needs_dept_head,
    apply_contract_outsource_biz_dept_head,
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
