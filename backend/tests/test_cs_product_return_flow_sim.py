# -*- coding: utf-8 -*-
"""售出产品/工具退回：路由 + 审批人模拟。"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.domains.lowcode._customer_service_jdy_generated import CUSTOMER_SERVICE_JDY
from app.domains.lowcode.approver_resolver import ApprovalContext, ApproverResolver
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import apply_cs_product_return_approvers
from tests.lead_intel_helpers import DEMO_TENANT

# 会签成员 field_18 中的简道云部门/组 ID（见 workflows_raw n20 条件）
DEPT_QC = "5b18a7b8258e41557b07f6e2"
DEPT_PROD = "56ca5bacf83c32e4699dd192"
DEPT_PURCHASE = "619af35c8fb9780008059d3d"
DEPT_PURCHASE2 = "645af34b67c48d0008d855ff"

NO_TRANSFER = {"field_26": "否"}


def _graph():
    d = CUSTOMER_SERVICE_JDY["cs_product_return"]
    nodes = copy.deepcopy(d["flow_nodes"])
    routes = copy.deepcopy(d["flow_routes"])
    apply_cs_product_return_approvers(nodes)
    return SimpleNamespace(node_definitions=nodes, route_definitions=routes)


def _eng():
    return WorkflowEngine(db=None, tenant_id="t")


def _next(node_id: str, form_data: dict | None = None) -> list[str]:
    return _eng()._next_targets(_graph(), node_id, form_data or {})


def _walk(form_data: dict, max_steps: int = 40) -> list[str]:
    eng, ver = _eng(), _graph()
    path, cur, seen = [], "start", set()
    for _ in range(max_steps):
        if cur in seen or cur == "end":
            break
        seen.add(cur)
        path.append(cur)
        nxt = eng._next_targets(ver, cur, form_data)
        if not nxt:
            break
        cur = nxt[0]
    if cur == "end" and path and path[-1] != "end":
        path.append("end")
    return path


@pytest.mark.parametrize("form_data,expect", [
    ({**NO_TRANSFER, "field_3": "材质鉴定"}, "n15"),
    ({**NO_TRANSFER, "field_3": "工具退回"}, "n17"),
    ({**NO_TRANSFER, "field_3": "退回及维修再发货"}, "n15"),
    ({"field_26": "是", "field_27": ["u1"]}, "n29"),
])
def test_start_routing(form_data, expect):
    assert _next("start", form_data) == [expect]


def test_n17_material_vs_warehouse():
    assert _next("n17", {"field_3": "材质鉴定"}) == ["n3"]
    assert _next("n17", {"field_3": "工具退回"}) == ["n2__1"]


@pytest.mark.parametrize("field_18,expect", [
    (DEPT_QC, "n4"),
    (DEPT_PROD, "n23"),
    (DEPT_PURCHASE, "n24"),
    (DEPT_PURCHASE2, "n32"),
])
def test_n20_repair_branch_by_countersign(field_18, expect):
    fd = {"field_3": "退回及维修再发货", "field_18": [field_18]}
    assert _next("n20", fd) == [expect]


def test_n20_tool_return_end():
    assert _next("n20", {"field_3": "工具退回"}) == ["end"]


def test_path_material_identification():
    path = _walk({**NO_TRANSFER, "field_3": "材质鉴定"})
    assert path[-8:] == ["n15", "n17", "n3", "n21", "n5", "n12__2", "n19__2", "end"]


def test_path_tool_return():
    path = _walk({**NO_TRANSFER, "field_3": "工具退回"})
    assert path == ["start", "n17", "n2__1", "n28__1", "n20", "end"]


def test_path_transfer_to_related():
    path = _walk({"field_26": "是", "field_27": ["u1"]})
    assert path[:3] == ["start", "n29", "n31"]


def test_path_repair_via_qc():
    fd = {**NO_TRANSFER, "field_3": "退回及维修再发货", "field_18": [DEPT_QC]}
    path = _walk(fd)
    assert "n20" in path and "n4" in path and path[-1] == "end"


@pytest.mark.asyncio
async def test_cs_return_approvers_resolve(db):
    from app.domains.auth.models import User
    from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
    from app.domains.lowcode import service as lc

    tenant = DEMO_TENANT
    await lc.ensure_builtin_form(db, tenant, "cs_product_return", {"sub": "admin"})
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant,
        WfProcessDefinition.code == "SYS_CS_PRODUCT_RETURN",
    ))).scalar_one()
    v = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.process_definition_id == d.id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one()
    nodes = {n["id"]: n for n in (v.node_definitions or []) if isinstance(n, dict)}

    sp_id = (await db.execute(text(
        "SELECT id FROM users WHERE tenant_id = :t AND is_active = true LIMIT 1"
    ), {"t": tenant})).scalar_one()
    ctx = ApprovalContext(
        initiator_id=sp_id,
        form_data={
            "field_18": [sp_id],
            "field_19": sp_id,
            "field_20": sp_id,
            "field_21": sp_id,
            "field_22": sp_id,
            "field_27": [sp_id],
            "field": sp_id,
        },
    )
    resolver = ApproverResolver(db, tenant)
    checks = [
        ("n3", "客服办理"),
        ("n20", "客服办理2"),
        ("n4", "质检"),
        ("n5", "财务判定"),
        ("n17", "物流中心"),
        ("n2__1", "仓库接收"),
    ]
    failures = []
    for nid, label in checks:
        node = nodes.get(nid)
        if not node:
            failures.append(f"{label}: 节点缺失")
            continue
        rule = node.get("approver_rule") or {}
        assert rule.get("type") in ("specified_user", "form_field_person"), f"{label} {rule}"
        ids = await resolver.resolve(rule, ctx)
        # CI seed 无钉钉 username 时 specified_user 解析为空（节点 empty_strategy=auto_approve）
        if ids:
            names = (await db.execute(select(User.real_name).where(User.id.in_(ids)))).scalars().all()
            print(f"  OK {label} -> {list(names)}")

    for nid in ("n3", "n20"):
        rule = nodes[nid]["approver_rule"]
        assert rule["type"] == "specified_user"
        assert isinstance(rule["value"], list)
        assert len(rule["value"]) == 4

    if failures:
        pytest.fail("\n".join(failures))


def test_cs_product_return_initiator_defaults():
    """提交人/发起部门应默认当前用户及主部门。"""
    defs = {f["id"]: f for f in CUSTOMER_SERVICE_JDY["cs_product_return"]["field_definitions"]}
    assert defs["field"]["props"]["default_current_user"] is True
    assert defs["field_2"]["props"]["default_current_dept"] is True
    assert defs["field"].get("form_editable") is False


def test_cs_product_return_warehouse_judge_not_at_create():
    """明细「仓库判定*」发起不可填，审批节点填写。"""
    f7 = next(
        f for f in CUSTOMER_SERVICE_JDY["cs_product_return"]["field_definitions"]
        if f["id"] == "field_7"
    )
    col = next(c for c in f7["detail_table_columns"] if c["id"] == "field_14")
    assert col["available_on_create"] is False
    assert col["fill_stage"] == "approver"
    assert col["required"] is True


def test_cs_product_return_approver_section_not_at_create():
    """「审批填写」区：发起 optAuth 未授权，创建页不展示。"""
    defs = {f["id"]: f for f in CUSTOMER_SERVICE_JDY["cs_product_return"]["field_definitions"]}
    for fid in ("field_18", "field_19", "field_20", "field_21", "field_22",
                "field_23", "f_1", "field_24", "field_25"):
        assert defs[fid].get("available_on_create") is False, fid
        assert defs[fid].get("fill_stage") == "approver", fid
