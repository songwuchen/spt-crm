# -*- coding: utf-8 -*-
"""售出产品退回：客服办理后「会签人员」按人选并行分流。"""
from __future__ import annotations

from app.domains.lowcode.workflow_engine import WorkflowEngine, evaluate_condition
from app.domains.lowcode.workflow_service import (
    apply_cs_product_return_n20_countersign_routes,
    _flow_cs_product_return_needs_n20_route_fix,
)

# 与 smoke / 简道云一致
DEPT_QC = "5b18a7b8258e41557b07f6e2"
DEPT_PROD = "56ca5bacf83c32e4699dd192"
DEPT_PURCHASE = "619af35c8fb9780008059d3d"
DEPT_PURCHASE2 = "645af34b67c48d0008d855ff"
U_QC = "191811255038139135"  # 韩小超
U_PROD = "02364437547295"  # 吕英萍
U_PURCHASE = "054351591124488512"  # 张蒙蒙
U_PURCHASE2 = "1135263833366065"  # 苏金泓


def _routes_legacy() -> list[dict]:
    return [
        {
            "id": "r_2", "source": "n20", "target": "end",
            "condition": {"field": "field_3", "operator": "in", "value": ["工具退回"]},
            "exclusive_group": "ex_n20",
        },
        {
            "id": "r_5", "source": "n20", "target": "n4",
            "condition": {
                "rel": "and",
                "cond": [
                    {"field": "field_3", "operator": "in", "value": ["退回及维修再发货"]},
                    {"field": "field_18", "operator": "in", "value": [DEPT_QC]},
                ],
            },
            "exclusive_group": "ex_n20",
        },
        {
            "id": "r_21", "source": "n20", "target": "n23",
            "condition": {
                "rel": "and",
                "cond": [
                    {"field": "field_3", "operator": "in", "value": ["退回及维修再发货"]},
                    {"field": "field_18", "operator": "in", "value": [DEPT_PROD]},
                ],
            },
            "exclusive_group": "ex_n20",
        },
        {
            "id": "r_22", "source": "n20", "target": "n24",
            "condition": {
                "rel": "and",
                "cond": [
                    {"field": "field_3", "operator": "in", "value": ["退回及维修再发货"]},
                    {"field": "field_18", "operator": "in", "value": [DEPT_PURCHASE]},
                ],
            },
            "exclusive_group": "ex_n20",
        },
        {
            "id": "r_29", "source": "n20", "target": "n32",
            "condition": {
                "rel": "and",
                "cond": [
                    {"field": "field_3", "operator": "in", "value": ["退回及维修再发货"]},
                    {"field": "field_18", "operator": "in", "value": [DEPT_PURCHASE2]},
                ],
            },
            "exclusive_group": "ex_n20",
        },
    ]


def test_n20_route_fix_detects_legacy():
    assert _flow_cs_product_return_needs_n20_route_fix(_routes_legacy())


def test_n20_route_fix_applies_person_parallel():
    routes = _routes_legacy()
    assert apply_cs_product_return_n20_countersign_routes(routes)
    assert not _flow_cs_product_return_needs_n20_route_fix(routes)
    by = {r["id"]: r for r in routes}
    for rid, uname, dept in (
        ("r_5", U_QC, DEPT_QC),
        ("r_21", U_PROD, DEPT_PROD),
        ("r_22", U_PURCHASE, DEPT_PURCHASE),
        ("r_29", U_PURCHASE2, DEPT_PURCHASE2),
    ):
        r = by[rid]
        assert r.get("fork") == "parallel"
        assert not r.get("exclusive_group")
        vals = []
        cond = r["condition"]
        for c in cond["cond"]:
            if c.get("field") == "field_18":
                vals = c.get("value") or []
        assert uname in vals and dept in vals


def test_n20_next_targets_person_multi_parallel():
    routes = _routes_legacy()
    apply_cs_product_return_n20_countersign_routes(routes)
    ver = type("V", (), {"route_definitions": routes, "node_definitions": []})()
    eng = WorkflowEngine(db=None, tenant_id="t")
    # 会签人员：韩小超 + 吕英萍 + 苏金泓（username，模拟 _form_data 别名展开后）
    fd = {
        "field_3": "退回及维修再发货",
        "field_18": [U_QC, U_PROD, U_PURCHASE2],
    }
    got = eng._next_targets(ver, "n20", fd)
    assert set(got) == {"n4", "n23", "n32"}


def test_n20_next_targets_dept_id_still_works():
    routes = _routes_legacy()
    apply_cs_product_return_n20_countersign_routes(routes)
    ver = type("V", (), {"route_definitions": routes, "node_definitions": []})()
    eng = WorkflowEngine(db=None, tenant_id="t")
    got = eng._next_targets(ver, "n20", {
        "field_3": "退回及维修再发货",
        "field_18": [DEPT_QC],
    })
    assert got == ["n4"]


def test_n20_tool_return_still_ends():
    routes = _routes_legacy()
    apply_cs_product_return_n20_countersign_routes(routes)
    ver = type("V", (), {"route_definitions": routes, "node_definitions": []})()
    eng = WorkflowEngine(db=None, tenant_id="t")
    assert eng._next_targets(ver, "n20", {"field_3": "工具退回"}) == ["end"]
