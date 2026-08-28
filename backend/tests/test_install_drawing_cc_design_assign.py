"""安装图设计通知：抄送设计指派1/2 回归。"""
from app.domains.lowcode.workflow_service import (
    _install_drawing_cc_design_assign_rule_ok,
    apply_install_drawing_cc_design_assign,
)


def test_install_drawing_cc_design_assign_rule_mixed():
    ok = {
        "type": "mixed",
        "value": [
            {"type": "specified_user", "value": "02364335378133"},
            {"type": "form_field_person", "value": "order_person"},
            {"type": "form_field_person", "value": "design_assignees"},
            {"type": "creator"},
        ],
    }
    assert _install_drawing_cc_design_assign_rule_ok(ok)
    assert not _install_drawing_cc_design_assign_rule_ok({"type": "creator"})


def test_apply_install_drawing_cc_design_assign_patches_named_nodes():
    nodes = [
        {"id": "n6__1", "type": "cc", "name": "抄送设计指派1", "approver_rule": {"type": "creator"}},
        {"id": "n14__2", "type": "cc", "name": "抄送设计指派2", "approver_rule": {"type": "creator"}},
        {"id": "n8", "type": "cc", "name": "抄送订货人", "approver_rule": {"type": "form_field_person", "value": "order_person"}},
    ]
    assert apply_install_drawing_cc_design_assign(nodes)
    assert _install_drawing_cc_design_assign_rule_ok(nodes[0]["approver_rule"])
    assert _install_drawing_cc_design_assign_rule_ok(nodes[1]["approver_rule"])
    assert nodes[2]["approver_rule"] == {"type": "form_field_person", "value": "order_person"}


def test_apply_install_drawing_cc_design_assign_idempotent():
    nodes = [
        {
            "id": "n6__1",
            "type": "cc",
            "name": "抄送设计指派1",
            "approver_rule": {
                "type": "mixed",
                "value": [
                    {"type": "specified_user", "value": "02364335378133"},
                    {"type": "form_field_person", "value": "order_person"},
                    {"type": "form_field_person", "value": "design_assignees"},
                    {"type": "creator"},
                ],
            },
        },
    ]
    assert not apply_install_drawing_cc_design_assign(nodes)
