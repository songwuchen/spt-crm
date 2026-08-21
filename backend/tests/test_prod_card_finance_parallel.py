# -*- coding: utf-8 -*-
"""生产卡：财务核价后安排设计/通知生产应对齐简道云并行，不能互斥只走一条。"""
import copy
from types import SimpleNamespace

from app.domains.lowcode._prod_card_jdy_generated import PROD_CARD_JDY
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import (
    _flow_prod_card_finance_not_parallel,
    apply_prod_card_finance_branch_parallel,
)


def _prod_card_graph():
    pack = PROD_CARD_JDY["prod_card_supplement"]
    return copy.deepcopy(pack["flow_nodes"]), copy.deepcopy(pack["flow_routes"])


def _node_id(nodes, name: str) -> str:
    for n in nodes:
        if n.get("name") == name:
            return str(n["id"])
    raise AssertionError(name)


def test_prod_card_finance_routes_still_exclusive_before_fix():
    nodes, routes = _prod_card_graph()
    assert _flow_prod_card_finance_not_parallel(nodes, routes)


def test_need_research_drawing_hits_design_not_only_notify_prod():
    nodes, routes = _prod_card_graph()
    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    finance_id = _node_id(nodes, "财务核价")
    design_id = _node_id(nodes, "安排设计1")
    notify_id = _node_id(nodes, "通知生产")

    before = set(eng._next_targets(version, finance_id, {
        "need_research_drawing": "是",
        "is_robot": "否",
    }))
    assert notify_id in before
    assert design_id not in before

    assert apply_prod_card_finance_branch_parallel(nodes, routes)
    assert not _flow_prod_card_finance_not_parallel(nodes, routes)

    after = set(eng._next_targets(version, finance_id, {
        "need_research_drawing": "是",
        "is_robot": "否",
    }))
    assert design_id in after
    assert notify_id in after


def test_robot_yes_skips_design_and_notify_prod():
    nodes, routes = _prod_card_graph()
    apply_prod_card_finance_branch_parallel(nodes, routes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    finance_id = _node_id(nodes, "财务核价")
    factory_id = _node_id(nodes, "小萌工厂")

    targets = set(eng._next_targets(version, finance_id, {"is_robot": "是"}))
    assert factory_id in targets
    assert _node_id(nodes, "安排设计1") not in targets
    assert _node_id(nodes, "通知生产") not in targets
