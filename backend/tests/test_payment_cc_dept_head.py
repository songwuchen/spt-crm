"""收款登记抄送部门负责人补丁回归。"""
from app.domains.lowcode.workflow_service import (
    _approver_rule_has_sub,
    _flow_payment_cc_needs_dept_head,
    apply_payment_registration_cc_dept_head,
)


def test_payment_cc_patches_n24_n25_and_n27():
    nodes = [
        {
            "id": "n24",
            "type": "cc",
            "name": "抄送节点",
            "approver_rule": {
                "type": "specified_user",
                "value": ["023641581817", "manager2820"],
            },
        },
        {
            "id": "n25",
            "type": "cc",
            "name": "抄送节点",
            "approver_rule": {
                "type": "specified_user",
                "value": ["023641581817"],
            },
        },
        {
            "id": "n27",
            "type": "cc",
            "name": "迅焊抄送",
            "approver_rule": {
                "type": "specified_user",
                "value": ["02352513566524"],
            },
        },
    ]
    assert _flow_payment_cc_needs_dept_head(nodes)
    assert apply_payment_registration_cc_dept_head(nodes)

    n24_rule = nodes[0]["approver_rule"]
    assert n24_rule["type"] == "mixed"
    assert _approver_rule_has_sub(n24_rule, {
        "type": "form_field_person_dept_head",
        "value": "sales_person",
    })
    assert _approver_rule_has_sub(n24_rule, {
        "type": "specified_user",
        "value": ["023641581817", "manager2820"],
    })

    n27_rule = nodes[2]["approver_rule"]
    assert _approver_rule_has_sub(n27_rule, {"type": "dept_head"})

    assert not _flow_payment_cc_needs_dept_head(nodes)
    assert not apply_payment_registration_cc_dept_head(nodes)
