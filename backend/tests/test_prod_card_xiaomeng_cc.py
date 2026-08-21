# -*- coding: utf-8 -*-
"""生产卡：小萌工厂 → 杨霜；审完抄送三人 ∥ 结束（无转电气车间）。"""
import copy
from types import SimpleNamespace

from app.domains.lowcode._prod_card_jdy_generated import PROD_CARD_JDY
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import (
    _PROD_XIAOMENG_APPROVER,
    _PROD_XIAOMENG_CC_NODE_ID,
    _PROD_XIAOMENG_CC_NODE_NAME,
    _PROD_XIAOMENG_CC_RULE,
    _approver_rule_matches,
    _flow_prod_card_xiaomeng_needs_fix,
    apply_prod_card_finance_branch_parallel,
    apply_prod_card_xiaomeng_yangshuang_cc,
)


def _graph():
    pack = PROD_CARD_JDY["prod_card_supplement"]
    return copy.deepcopy(pack["flow_nodes"]), copy.deepcopy(pack["flow_routes"])


def _node_id(nodes, name: str) -> str:
    for n in nodes:
        if n.get("name") == name:
            return str(n["id"])
    raise AssertionError(name)


def test_xiaomeng_needs_fix_before_patch():
    nodes, routes = _graph()
    assert _flow_prod_card_xiaomeng_needs_fix(nodes, routes)


def test_xiaomeng_yangshuang_and_parallel_cc_end():
    nodes, routes = _graph()
    apply_prod_card_finance_branch_parallel(nodes, routes)
    assert apply_prod_card_xiaomeng_yangshuang_cc(nodes, routes)
    assert not _flow_prod_card_xiaomeng_needs_fix(nodes, routes)
    assert not apply_prod_card_xiaomeng_yangshuang_cc(nodes, routes)

    xm = next(n for n in nodes if n.get("name") == "小萌工厂")
    assert _approver_rule_matches(xm.get("approver_rule") or {}, _PROD_XIAOMENG_APPROVER)
    assert not xm.get("cc_rule")
    assert not xm.get("multi_mode")

    cc = next(n for n in nodes if n.get("id") == _PROD_XIAOMENG_CC_NODE_ID)
    assert cc.get("type") == "cc"
    assert cc.get("name") == _PROD_XIAOMENG_CC_NODE_NAME
    assert _approver_rule_matches(cc.get("approver_rule") or {}, _PROD_XIAOMENG_CC_RULE)

    xm_id = str(xm["id"])
    outs = {(r.get("target"), bool(r.get("always"))) for r in routes if r.get("source") == xm_id}
    assert ("end", False) in outs or any(
        r.get("source") == xm_id and r.get("target") == "end" for r in routes
    )
    assert any(
        r.get("source") == xm_id and r.get("target") == _PROD_XIAOMENG_CC_NODE_ID and r.get("always")
        for r in routes
    )
    # 不加转电气车间出边
    assert not any(
        r.get("source") == xm_id and "电气" in str(
            next((n.get("name") for n in nodes if n.get("id") == r.get("target")), "")
        )
        for r in routes
    )

    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    targets = set(eng._next_targets(version, xm_id, {}))
    assert "end" in targets
    assert _PROD_XIAOMENG_CC_NODE_ID in targets
