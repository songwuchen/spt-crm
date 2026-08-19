"""售前服务通知流程补丁回归。"""
from app.domains.lowcode.workflow_service import (
    _presale_cc_rule_ok,
    apply_presale_cc_initiator_and_applicant,
)


def test_presale_cc_rule_mixed_creator_and_applicant():
    ok = {
        "type": "mixed",
        "value": [
            {"type": "creator"},
            {"type": "form_field_person", "value": "applicant"},
        ],
    }
    assert _presale_cc_rule_ok(ok)
    assert not _presale_cc_rule_ok({"type": "creator"})


def test_apply_presale_cc_patches_all_cc_nodes():
    nodes = [
        {"id": "n9", "type": "cc", "name": "抄送节点", "approver_rule": {"type": "creator"}},
        {"id": "n2", "type": "approval", "name": "总工审批", "approver_rule": {"type": "creator"}},
        {"id": "n10", "type": "cc", "name": "抄送节点", "approver_rule": {"type": "creator"}},
    ]
    assert apply_presale_cc_initiator_and_applicant(nodes)
    for n in nodes:
        if n["type"] == "cc":
            assert _presale_cc_rule_ok(n["approver_rule"])
    assert nodes[1]["approver_rule"] == {"type": "creator"}


def test_apply_presale_cc_idempotent():
    nodes = [
        {
            "id": "n9",
            "type": "cc",
            "approver_rule": {
                "type": "mixed",
                "value": [
                    {"type": "creator"},
                    {"type": "form_field_person", "value": "applicant"},
                ],
            },
        },
    ]
    assert not apply_presale_cc_initiator_and_applicant(nodes)
