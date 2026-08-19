# -*- coding: utf-8 -*-
"""售出产品更换（补发）流程：路由分支 + 审批人解析 模拟回归。"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.domains.lowcode._customer_service_jdy_generated import CUSTOMER_SERVICE_JDY
from app.domains.lowcode.approver_resolver import ApprovalContext, ApproverResolver
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_service import apply_cs_product_replace_approvers
from tests.lead_intel_helpers import DEMO_TENANT

# 简道云部门 / 人员常量（与 _dump_cs_replace_routes 一致）
DEPT_XIAO = "56ca5b8af97e80434fc06128"
DEPT_THERMAL = "59dc5c5f0b18743912395106"
SALES_GUOCHUN = "6603dadbd23d27d4d03d8824"


def _graph():
    d = CUSTOMER_SERVICE_JDY["cs_product_replace"]
    nodes = copy.deepcopy(d["flow_nodes"])
    routes = copy.deepcopy(d["flow_routes"])
    apply_cs_product_replace_approvers(nodes)
    return SimpleNamespace(node_definitions=nodes, route_definitions=routes)


def _eng():
    return WorkflowEngine(db=None, tenant_id="t")


def _next(node_id: str, form_data: dict | None = None) -> list[str]:
    return _eng()._next_targets(_graph(), node_id, form_data or {})


# ---------- 发起后首节点（ex_start 互斥） ----------

@pytest.mark.parametrize("form_data,expect", [
    ({"field_22": "是"}, "n9"),
    ({"field": DEPT_XIAO, "field_22": "否"}, "n12"),
    ({"field": DEPT_THERMAL, "field_22": "否"}, "n17"),
    ({"field_24": "是", "sales_person": "other-user"}, "n19__1"),
    ({"field_24": "是", "sales_person": SALES_GUOCHUN}, "n23__2"),
    ({"field_2": "regional-mgr-id", "field_22": "否"}, "n24"),
    ({"field": "ordinary-dept", "sales_person": "u1"}, "n1"),
])
def test_start_routing_branches(form_data, expect):
    assert _next("start", form_data) == [expect]


def test_start_field_22_takes_priority_over_xiao():
    """需要补登=是 时，即使所属部门=小萌，也应直达客服补登。"""
    fd = {"field_22": "是", "field": DEPT_XIAO}
    assert _next("start", fd) == ["n9"]


def test_start_field_24_before_regional_manager():
    """迅焊=是 的分支排在「区域经理/组长非空」之前。"""
    fd = {"field_24": "是", "sales_person": "other", "field_2": "mgr"}
    assert _next("start", fd) == ["n19__1"]


# ---------- 中间节点 ----------

def test_n4_countersign_branch():
    assert _next("n4", {"field_25": "否"}) == ["n6"]
    assert _next("n4", {"field_25": "是"}) == ["n11"]


def test_n18_xunhan_finance_to_ceo():
    assert _next("n18", {"field_24": "是"}) == ["n21"]
    assert _next("n18", {}) == ["n8"]


def test_n9_end_and_handoff_branches():
    base = {"field_24": "否"}
    assert _next("n9", {**base, "field_28": "不需要", "field_23": "是"}) == ["end"]
    assert _next("n9", {**base, "field_28": "需要", "field_23": "否"}) == ["n15"]


def test_n9_xunhan_always_cc():
    fd = {"field_24": "是", "field_28": "不需要", "field_23": "是"}
    assert _next("n9", fd) == ["n22", "end"]


def test_n9_waits_until_handoff_fields_filled():
    """客服补登节点需填写转交/发货字段后才出边（与简道云一致）。"""
    assert _next("n9", {}) == []


# ---------- 总工 n6：__always 并行 + 条件互斥（对齐简道云） ----------

def test_n6_routing_parallel_ceo_with_finance_or_tech():
    """总工审批后：总经理 n8 为无条件并行；field_24=是 走技术 n20，否则走财务 n18。"""
    assert set(_next("n6", {})) == {"n8", "n18"}
    assert set(_next("n6", {"field_24": "是"})) == {"n8", "n20"}


def test_xunhan_path_includes_tech_finance_chain():
    """迅焊线（field_24=是）：部门经理 → … → 技术 → 财务 → 迅焊总经理 → 客服补登。"""
    eng = _eng()
    ver = _graph()
    fd = {
        "field_24": "是", "sales_person": "other", "field_25": "否",
        "field_28": "不需要", "field_23": "是",
    }
    cur = "start"
    path = []
    seen: set[str] = set()
    for _ in range(25):
        if cur in seen:
            break
        seen.add(cur)
        path.append(cur)
        nxt = eng._next_targets(ver, cur, fd)
        if not nxt:
            break
        cur = nxt[0]
    assert "n20" in path
    assert "n18" in path
    assert "n21" in path
    assert path[:4] == ["start", "n19__1", "n4", "n6"]


# ---------- 主路径走通（单链模拟） ----------

def _walk_primary(form_data: dict, *, max_steps: int = 25) -> list[str]:
    eng = _eng()
    ver = _graph()
    path: list[str] = []
    cur = "start"
    seen: set[str] = set()
    for _ in range(max_steps):
        if cur in seen or cur == "end":
            break
        seen.add(cur)
        path.append(cur)
        nxt = eng._next_targets(ver, cur, form_data)
        if not nxt:
            break
        cur = nxt[0]
    if cur == "end" and (not path or path[-1] != "end"):
        path.append("end")
    return path


@pytest.mark.parametrize("name,form_data,expect_tail", [
    (
        "标准线",
        {"field": "dept", "sales_person": "u1", "field_25": "否",
         "field_28": "不需要", "field_23": "是"},
        ["n1", "n4", "n6", "n18", "n8", "n9", "end"],
    ),
    (
        "小萌线",
        {"field": DEPT_XIAO, "field_22": "否", "field_25": "否",
         "field_28": "不需要", "field_23": "是"},
        ["n12", "n4", "n6", "n18", "n8", "n9", "end"],
    ),
    (
        "热能线",
        {"field": DEPT_THERMAL, "field_22": "否", "field_25": "否",
         "field_28": "不需要", "field_23": "是"},
        ["n17", "n4", "n6", "n18", "n8", "n9", "end"],
    ),
    (
        "直接补登",
        {"field_22": "是", "field_28": "不需要", "field_23": "是"},
        ["n9", "end"],
    ),
    (
        "补登后转交",
        {"field_22": "是", "field_28": "需要", "field_23": "否", "field_29": "handler"},
        ["n9", "n15", "n16", "end"],
    ),
    (
        "迅焊线",
        {
            "field_24": "是", "sales_person": "other", "field_25": "否",
            "field_28": "不需要", "field_23": "是",
        },
        ["n19__1", "n4", "n6", "n20", "n18", "n21", "n9", "n22"],
    ),
])
def test_primary_path_scenarios(name, form_data, expect_tail):
    path = _walk_primary(form_data)
    assert path[-len(expect_tail):] == expect_tail, f"{name}: {path}"


# ---------- 审批人（需本地库） ----------

@pytest.mark.asyncio
async def test_cs_replace_approvers_resolve_against_db(db):
    """关键节点审批人应能解析到活跃用户（非空、非 auto_approve 兜底）。"""
    from app.database import generate_uuid
    from app.domains.auth.models import User
    from app.domains.organization.models import Department, UserDepartment
    from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
    from app.domains.lowcode import service as lc

    tenant = DEMO_TENANT
    await lc.ensure_builtin_form(db, tenant, "cs_product_replace", {"sub": "admin"})
    d = (await db.execute(select(WfProcessDefinition).where(
        WfProcessDefinition.tenant_id == tenant,
        WfProcessDefinition.code == "SYS_CS_PRODUCT_REPLACE",
    ))).scalar_one()
    v = (await db.execute(select(WfProcessDefinitionVersion).where(
        WfProcessDefinitionVersion.process_definition_id == d.id,
        WfProcessDefinitionVersion.status == "published",
    ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one()

    nodes = {n["id"]: n for n in (v.node_definitions or []) if isinstance(n, dict)}
    resolver = ApproverResolver(db, tenant)

    # 找一位有部门的业务员用于 n1 部门负责人；CI seed 通常没有「业务员≠负责人」，则自建
    sp_row = (await db.execute(text("""
        SELECT u.id, u.real_name, ud.department_id, d.leader_id
        FROM users u
        JOIN user_departments ud ON ud.user_id = u.id AND ud.tenant_id = :t
        JOIN departments d ON d.id = ud.department_id
        WHERE u.tenant_id = :t AND u.is_active = true
          AND d.leader_id IS NOT NULL AND u.id != d.leader_id
        LIMIT 1
    """), {"t": tenant})).first()

    created_ids: list[str] = []
    created_dept_ids: list[str] = []
    if sp_row:
        sp_id, _sp_name, dept_id, leader_id = sp_row
    else:
        leader_id = generate_uuid()
        sp_id = generate_uuid()
        dept_id = generate_uuid()
        db.add(User(
            id=leader_id, tenant_id=tenant, username="cs_replace_leader",
            real_name="更换流程部门负责人", password_hash="x", is_active=True,
        ))
        db.add(User(
            id=sp_id, tenant_id=tenant, username="cs_replace_salesperson",
            real_name="更换流程业务员", password_hash="x", is_active=True,
        ))
        db.add(Department(
            id=dept_id, tenant_id=tenant, name="更换流程测试部",
            path="/更换流程测试部/", sort_order=0, leader_id=leader_id,
        ))
        db.add(UserDepartment(
            id=generate_uuid(), tenant_id=tenant, user_id=leader_id, department_id=dept_id,
        ))
        db.add(UserDepartment(
            id=generate_uuid(), tenant_id=tenant, user_id=sp_id, department_id=dept_id,
        ))
        await db.commit()
        created_ids = [leader_id, sp_id]
        created_dept_ids = [dept_id]

    try:
        ctx = ApprovalContext(
            initiator_id=sp_id,
            form_data={
                "sales_person": sp_id,
                "field": dept_id,
                "field_2": sp_id,
                "field_26": sp_id,
                "field_29": sp_id,
            },
        )

        checks = [
            ("n1", "业务经理审批·部门负责人"),
            ("n4", "客服会签·4人或签"),
            ("n6", "总工审批"),
            ("n8", "总经理审批"),
            ("n18", "财务核算"),
        ]
        failures = []
        for nid, label in checks:
            node = nodes.get(nid)
            if not node:
                failures.append(f"{label}: 节点 {nid} 缺失")
                continue
            rule = node.get("approver_rule") or {}
            try:
                ids = await resolver.resolve(rule, ctx)
            except Exception as exc:
                failures.append(f"{label}: 解析异常 {exc}")
                continue
            if ids:
                names = (await db.execute(
                    select(User.real_name).where(User.id.in_(ids))
                )).scalars().all()
                print(f"  OK {label} -> {list(names)} ({len(ids)}人)")
            elif rule.get("type") != "specified_user":
                failures.append(f"{label}: 审批人为空 rule={rule}")

        if failures:
            pytest.fail("\n".join(failures))

        # n1 应解析到部门负责人（且业务员本人被 exclude_initiator 排除）
        n1_ids = await resolver.resolve(nodes["n1"]["approver_rule"], ctx)
        assert leader_id in n1_ids
        assert sp_id not in n1_ids

        # 热能线业务经理(段荣凯)：种子库有该 username 时才断言能解析
        n17_rule = nodes["n17"]["approver_rule"]
        n17_ids = await resolver.resolve(n17_rule, ctx)
        want = n17_rule.get("value")
        if want:
            exists = (await db.execute(
                select(User.id).where(User.tenant_id == tenant, User.username == str(want))
            )).scalar_one_or_none()
            if exists:
                assert n17_ids, "热能线业务经理(段荣凯)应能解析"
    finally:
        if created_ids:
            await db.execute(text(
                "DELETE FROM user_departments WHERE user_id = ANY(:uids)"
            ), {"uids": created_ids})
            await db.execute(text(
                "DELETE FROM users WHERE id = ANY(:uids)"
            ), {"uids": created_ids})
        if created_dept_ids:
            await db.execute(text(
                "DELETE FROM departments WHERE id = ANY(:ids)"
            ), {"ids": created_dept_ids})
        if created_ids or created_dept_ids:
            await db.commit()
