"""节点操作配置。"""
from app.domains.lowcode.wf_node_actions import node_action_allowed, parse_node_actions


def test_parse_node_actions_defaults():
    assert parse_node_actions(None)["submit"] is True
    assert parse_node_actions({})["reject"] is False
    assert parse_node_actions({})["return"] is True
    assert parse_node_actions({})["submit_print"] is False


def test_parse_node_actions_lead_keeps_reject():
    assert parse_node_actions(None, biz_type="lead")["reject"] is True
    assert parse_node_actions({}, biz_type="lead_reactivation")["reject"] is True
    assert parse_node_actions(None, biz_type="contract_version")["reject"] is False


def test_parse_node_actions_override():
    acts = parse_node_actions({"node_actions": {"reject": False, "transfer": False}})
    assert acts["reject"] is False
    assert acts["transfer"] is False
    assert acts["submit"] is True


def test_node_action_allowed():
    node = {"node_actions": {"save": False}}
    assert node_action_allowed(node, "save") is False
    assert node_action_allowed(node, "submit") is True
    assert node_action_allowed(node, "reject", biz_type="form_instance") is False
    assert node_action_allowed(node, "reject", biz_type="lead") is True


def test_drawing_requisition_arrange_submit_print():
    node = {"name": "研究院安排", "type": "approval"}
    acts = parse_node_actions(node, form_code="drawing_requisition")
    assert acts["submit_print"] is True


def test_drawing_requisition_other_node_no_submit_print():
    node = {"name": "总工审批", "type": "approval"}
    acts = parse_node_actions(node, form_code="drawing_requisition")
    assert acts["submit_print"] is False


def test_prod_card_material_code_no_transfer():
    from app.domains.lowcode.wf_node_actions import (
        apply_prod_card_material_code_node_actions,
        is_prod_card_material_code_node,
    )

    assert is_prod_card_material_code_node("物料编码")
    assert not is_prod_card_material_code_node("产线-物料编码")

    node = {"name": "物料编码", "type": "approval"}
    acts = parse_node_actions(node, biz_type="prod_card_supplement")
    assert acts["transfer"] is False

    other = {"name": "财务核价", "type": "approval"}
    assert parse_node_actions(other, biz_type="prod_card_supplement")["transfer"] is True

    nodes = [
        {"id": "n5", "name": "物料编码", "type": "approval"},
        {"id": "n6", "name": "财务核价", "type": "approval", "node_actions": {"transfer": True}},
    ]
    assert apply_prod_card_material_code_node_actions(nodes) is True
    assert nodes[0]["node_actions"]["transfer"] is False
    assert nodes[1]["node_actions"]["transfer"] is True
    assert apply_prod_card_material_code_node_actions(nodes) is False
