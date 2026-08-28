# -*- coding: utf-8 -*-
"""生产卡：安排设计1 完成后应能进入物料编码（无转新乡/工艺包装人选）。"""
import copy

from types import SimpleNamespace

from app.domains.lowcode._prod_card_jdy_generated import PROD_CARD_JDY
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import (
    _flow_missing_prod_card_design1_material_route,
    apply_prod_card_design1_material_route,
    apply_prod_card_finance_branch_parallel,
    fix_packaging_fork_serial_priority,
)


def _prod_card_graph():
    pack = PROD_CARD_JDY["prod_card_supplement"]
    return copy.deepcopy(pack["flow_nodes"]), copy.deepcopy(pack["flow_routes"])


def _node_id(nodes, name: str) -> str:
    for n in nodes:
        if n.get("name") == name:
            return str(n["id"])
    raise AssertionError(name)


def _drop_design1_material_route(routes, design_id, material_id):
    routes[:] = [
        r for r in routes
        if not (
            isinstance(r, dict)
            and str(r.get("source")) == design_id
            and str(r.get("target")) == material_id
            and (r.get("condition") or {}).get("field") == "transfer_packaging_users"
            and (r.get("condition") or {}).get("operator") == "is_empty"
        )
    ]


def test_jdy_catalog_has_design1_material_route():
    nodes, routes = _prod_card_graph()
    assert not _flow_missing_prod_card_design1_material_route(nodes, routes)


def test_apply_restores_design1_material_route():
    nodes, routes = _prod_card_graph()
    design_id = _node_id(nodes, "安排设计1")
    material_id = _node_id(nodes, "物料编码")
    _drop_design1_material_route(routes, design_id, material_id)
    assert _flow_missing_prod_card_design1_material_route(nodes, routes)
    assert apply_prod_card_design1_material_route(nodes, routes)
    assert not _flow_missing_prod_card_design1_material_route(nodes, routes)
    assert not apply_prod_card_design1_material_route(nodes, routes)


def test_design1_hits_material_when_no_packaging_users():
    nodes, routes = _prod_card_graph()
    design_id = _node_id(nodes, "安排设计1")
    material_id = _node_id(nodes, "物料编码")
    _drop_design1_material_route(routes, design_id, material_id)
    apply_prod_card_design1_material_route(nodes, routes)
    fix_packaging_fork_serial_priority(nodes, routes)

    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    targets = eng._next_targets(version, design_id, {
        "design_dispatch": "总部单",
        "transfer_packaging_users": [],
    })
    assert material_id in targets


def test_v11_regression_graph_fixed_end_to_end():
    """模拟 V11 缺边：财务并行 + 安排设计1 后仅抄送，补边后应能进物料编码。"""
    nodes, routes = _prod_card_graph()
    apply_prod_card_finance_branch_parallel(nodes, routes)
    design_id = _node_id(nodes, "安排设计1")
    material_id = _node_id(nodes, "物料编码")
    _drop_design1_material_route(routes, design_id, material_id)
    assert _flow_missing_prod_card_design1_material_route(nodes, routes)

    assert apply_prod_card_design1_material_route(nodes, routes)
    fix_packaging_fork_serial_priority(nodes, routes)

    eng = WorkflowEngine(db=None, tenant_id="t")
    version = SimpleNamespace(route_definitions=routes, node_definitions=nodes)
    fd = {
        "need_research_drawing": "是",
        "is_robot": "否",
        "design_dispatch": "总部单",
        "transfer_packaging_users": [],
        "design_assignees": ["54caec9c-f85a-4d48-8ebb-8d70d217910e"],
    }
    finance_id = _node_id(nodes, "财务核价")
    assert _node_id(nodes, "安排设计1") in eng._next_targets(version, finance_id, fd)
    assert material_id in eng._next_targets(version, design_id, fd)
