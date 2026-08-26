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
