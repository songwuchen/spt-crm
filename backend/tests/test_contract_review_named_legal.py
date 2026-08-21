# -*- coding: utf-8 -*-
from app.domains.lowcode.workflow_service import (
    _contract_review_flow_graph,
    _contract_review_legal_users_aligned,
    _contract_review_finance_dir_aligned,
    _contract_review_parallel_countersign_aligned,
    apply_contract_review_named_legal_approvers,
)


def test_contract_review_legal_is_named_users():
    nodes, _ = _contract_review_flow_graph()
    by_id = {n["id"]: n for n in nodes}
    rule = by_id["approval_legal"]["approver_rule"]
    assert rule["type"] == "specified_user"
    assert rule["value"] == ["4723152427763414", "256932256424153873"]
    assert _contract_review_legal_users_aligned(nodes)


def test_contract_review_finance_dir_only_zhangguang():
    nodes, _ = _contract_review_flow_graph()
    by_id = {n["id"]: n for n in nodes}
    n = by_id["approval_finance_dir"]
    assert n["approver_rule"]["type"] == "specified_user"
    assert n["approver_rule"]["value"] == "0433406811775721"
    assert n.get("multi_mode", "or_sign") == "or_sign"
    assert _contract_review_finance_dir_aligned(nodes)
    # 旧会签配置应对齐失败
    bad = [{
        "id": "approval_finance_dir",
        "type": "approval",
        "approver_rule": {
            "type": "specified_user",
            "value": ["02362556584221", "0433406811775721"],
        },
        "multi_mode": "and_sign",
    }]
    assert not _contract_review_finance_dir_aligned(bad)


def test_apply_contract_review_named_legal_approvers():
    nodes = [{
        "id": "approval_legal",
        "type": "approval",
        "name": "法务审批",
        "approver_rule": {
            "type": "specified_role", "value": "legal", "exclude_initiator": True,
        },
        "empty_strategy": "auto_approve",
        "multi_mode": "or_sign",
    }]
    assert not _contract_review_legal_users_aligned(nodes)
    assert apply_contract_review_named_legal_approvers(nodes)
    assert nodes[0]["approver_rule"]["type"] == "specified_user"
    assert nodes[0]["approver_rule"]["value"] == [
        "4723152427763414", "256932256424153873",
    ]
    assert _contract_review_legal_users_aligned(nodes)
    assert not apply_contract_review_named_legal_approvers(nodes)


def test_contract_review_biz_fork_is_parallel():
    _, routes = _contract_review_flow_graph()
    assert _contract_review_parallel_countersign_aligned(routes)
    legal = next(
        r for r in routes
        if r.get("source") == "approval_biz" and r.get("target") == "approval_legal"
    )
    assert legal.get("fork") == "parallel"
    assert not any(
        r.get("source") == "approval_biz"
        and r.get("target") == "merge_review"
        for r in routes
    )
