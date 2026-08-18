"""开票申请：业务员抄送节点 + 列表数据范围并入 sales_person。"""
from __future__ import annotations

import pytest

from app.domains.lowcode.service import (
    _OWNER_PERSON_FIELD_BY_TEMPLATE,
    _instance_list_conds,
)
from app.domains.lowcode.workflow_service import (
    _INVOICE_CC_SALES_DONE,
    _INVOICE_CC_SALES_SUBMIT,
    _drawing_flow_graph,
    _flow_missing_invoice_sales_cc,
    apply_invoice_sales_cc,
)


def test_apply_invoice_sales_cc_idempotent():
    nodes = [
        {"id": "start", "type": "start", "name": "发起"},
        {"id": "n1", "type": "approval", "name": "开票"},
        {"id": "n4", "type": "approval", "name": "发起人接收"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes = [
        {"id": "r_2", "source": "start", "target": "n1"},
        {"id": "r_3", "source": "n1", "target": "n4", "always": True},
        {"id": "r_1", "source": "n4", "target": "end"},
    ]
    assert _flow_missing_invoice_sales_cc(nodes, routes) is True
    assert apply_invoice_sales_cc(nodes, routes) is True
    assert _flow_missing_invoice_sales_cc(nodes, routes) is False
    assert apply_invoice_sales_cc(nodes, routes) is False

    by_id = {n["id"]: n for n in nodes}
    assert by_id[_INVOICE_CC_SALES_SUBMIT]["type"] == "cc"
    assert by_id[_INVOICE_CC_SALES_SUBMIT]["approver_rule"] == {
        "type": "form_field_person", "value": "sales_person",
    }
    assert by_id[_INVOICE_CC_SALES_DONE]["name"] == "发票已开具可下载"
    edge = {(r["source"], r["target"], bool(r.get("always"))) for r in routes}
    assert ("start", _INVOICE_CC_SALES_SUBMIT, True) in edge
    assert ("n1", _INVOICE_CC_SALES_DONE, True) in edge


def test_drawing_flow_graph_invoice_includes_sales_cc():
    graph = _drawing_flow_graph("invoice_application")
    assert graph is not None
    nodes, routes = graph
    assert _flow_missing_invoice_sales_cc(nodes, routes) is False
    assert any(n.get("id") == _INVOICE_CC_SALES_SUBMIT for n in nodes)
    assert any(n.get("id") == _INVOICE_CC_SALES_DONE for n in nodes)


@pytest.mark.asyncio
async def test_advance_activates_invoice_approval_before_submit_cc():
    """start → 旁路抄送∥开票：抄送若先跑并无出边，旧引擎会误收尾，财务待办建不出来。"""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.domains.lowcode.workflow_engine import WorkflowEngine

    nodes = [
        {"id": "start", "type": "start", "name": "发起"},
        {"id": "n1", "type": "approval", "name": "开票"},
        {"id": "cc_sales_submit", "type": "cc", "name": "已提交开票申请"},
        {"id": "end", "type": "end", "name": "结束"},
    ]
    routes = [
        {"id": "r_2", "source": "start", "target": "n1"},
        {"id": "r_cc", "source": "start", "target": "cc_sales_submit", "always": True},
    ]
    version = SimpleNamespace(node_definitions=nodes, route_definitions=routes)
    eng = WorkflowEngine(db=None, tenant_id="t")
    order: list[str] = []

    async def _activate(inst, _version, node, _ctx, allow_reenter=False):
        order.append(node["id"])
        if node.get("type") == "cc":
            inst.status = "completed"

    eng._activate_node = AsyncMock(side_effect=_activate)
    inst = SimpleNamespace(status="running")
    await eng._advance(inst, version, "start", SimpleNamespace(form_data={}))
    assert order[0] == "n1"
    assert "cc_sales_submit" in order
    assert "end" not in order


def test_invoice_list_owner_person_field_mapping():
    assert _OWNER_PERSON_FIELD_BY_TEMPLATE["invoice_application"] == "sales_person"
    assert _OWNER_PERSON_FIELD_BY_TEMPLATE["quote_management"] == "sales_person"
    # 带 owner_person_field 时条件构造不抛错（SQL 表达式可编译）
    conds = _instance_list_conds(
        "t1", "tpl1", owner_ids=["u-sales"], owner_person_field="sales_person",
    )
    assert len(conds) >= 4
