"""Bulk-assign FUNCTION roles to users based on their DEPARTMENT (heuristic by name).

Run scripts.seed_function_roles FIRST (so the function roles exist), then INSIDE the
backend container:

    # 1) dry-run — prints 部门→角色 决策 + 统计 + 未匹配清单, writes nothing
    docker compose exec -T backend python -m scripts.assign_roles_by_dept
    # 2) apply (ADD the mapped function role to each user; idempotent)
    docker compose exec -T backend python -m scripts.assign_roles_by_dept --apply
    # 3) (optional, after verifying) also strip legacy/person-named roles
    docker compose exec -T backend python -m scripts.assign_roles_by_dept --apply --replace-legacy

Notes:
- A user's role is decided by the HIGHEST-priority keyword that matches any of their
  departments (see KEYWORD_ROLE). Department LEADERS are upgraded to the manager variant.
- Admins (role code 'admin') are never touched. Unmatched users are listed for manual fix.
- --replace-legacy removes a user's NON-function, non-admin roles (the 岳毅/王亚飞/马钢/test
  person-named bags). Without it, the function role is only ADDED.
- Review the dry-run 部门→角色 table and tweak KEYWORD_ROLE before --apply.
"""
import asyncio
import os
import sys
from collections import Counter, defaultdict

from sqlalchemy import select

from app.database import async_session_factory, generate_uuid
from app.domains.auth.models import User, Role, UserRole
from app.domains.organization.models import Department, UserDepartment

TENANT_ID = os.environ.get("TENANT_ID", "00000000-0000-0000-0000-000000000001")
APPLY = "--apply" in sys.argv
REPLACE_LEGACY = "--replace-legacy" in sys.argv
VERBOSE = "--verbose" in sys.argv

# First keyword that is a substring of a department name wins (order = priority).
KEYWORD_ROLE = [
    ("清欠", "collection_officer"),
    ("法务", "legal"),
    ("审计", "executive"),
    ("财务", "finance"),
    ("采购", "procurement"), ("外购", "procurement"),
    ("客户服务", "service_engineer"), ("售后", "service_engineer"), ("服务部", "service_engineer"),
    ("市场支持", "biz_support"), ("业务支持", "biz_support"), ("营销支持", "biz_support"), ("标书", "biz_support"),
    ("研究院", "design_engineer"), ("中央研究", "design_engineer"), ("技术", "design_engineer"),
    ("工艺", "design_engineer"), ("设计", "design_engineer"), ("质检", "design_engineer"),
    ("质量", "design_engineer"), ("标准化", "design_engineer"), ("试验", "design_engineer"),
    ("生产", "production"), ("车间", "production"), ("仓储", "production"), ("物流", "production"),
    ("装卸", "production"), ("涂装", "production"), ("电气", "production"), ("下料", "production"),
    ("整装", "production"), ("机加工", "production"), ("筛板", "production"), ("配送", "production"),
    ("工厂", "production"), ("制作", "production"), ("装备", "production"),
    ("国际", "sales_rep"), ("贸易", "sales_rep"), ("营销", "sales_rep"),
    ("事业部", "sales_rep"), ("销售", "sales_rep"),
    ("总经办", "executive"), ("总经理", "executive"),
    # explicitly unmapped (no obvious CRM role) -> manual:
    ("人力", None), ("信息情报", None), ("公共事务", None), ("研发中心", None),
]

MANAGER_VARIANT = {
    "sales_rep": "sales_manager",
    "production": "production_manager",
    "service_engineer": "service_manager",
    "finance": "finance_manager",
}

FUNCTION_CODES = {
    "sales_rep", "sales_manager", "sales_director", "biz_support", "design_engineer",
    "tech_chief", "production", "production_manager", "finance", "finance_manager",
    "collection_officer", "service_engineer", "service_manager", "procurement",
    "legal", "executive",
}


def role_for_dept_name(name: str):
    """Return (role_code_or_None, priority_index, matched_keyword) or (None, 9999, None)."""
    for i, (kw, code) in enumerate(KEYWORD_ROLE):
        if kw in (name or ""):
            return code, i, kw
    return None, 9999, None


async def main():
    async with async_session_factory() as db:
        depts = (await db.execute(
            select(Department).where(Department.tenant_id == TENANT_ID)
        )).scalars().all()
        dept_by_id = {d.id: d for d in depts}
        leader_ids = {d.leader_id for d in depts if d.leader_id}

        roles = (await db.execute(
            select(Role).where(Role.tenant_id == TENANT_ID)
        )).scalars().all()
        role_id_by_code = {r.code: r.id for r in roles}
        role_code_by_id = {r.id: r.code for r in roles}

        users = (await db.execute(
            select(User).where(User.tenant_id == TENANT_ID, User.is_active == True)  # noqa: E712
        )).scalars().all()
        user_depts = defaultdict(list)
        for ud in (await db.execute(
            select(UserDepartment).where(UserDepartment.tenant_id == TENANT_ID)
        )).scalars().all():
            user_depts[ud.user_id].append(ud.department_id)
        user_roles = defaultdict(list)
        for ur in (await db.execute(
            select(UserRole).where(UserRole.tenant_id == TENANT_ID)
        )).scalars().all():
            user_roles[ur.user_id].append(ur)

        # ---- department -> role decision table ----
        member_count = Counter()
        for uid, dids in user_depts.items():
            for did in dids:
                member_count[did] += 1
        print(f"tenant={TENANT_ID}  mode={'APPLY' if APPLY else 'DRY-RUN'}"
              + (" +replace-legacy" if REPLACE_LEGACY else "") + "\n")
        print("=== 部门 → 角色 (仅列有成员的部门) ===")
        dept_decision = {}
        for d in sorted(depts, key=lambda x: x.path or ""):
            code, _, kw = role_for_dept_name(d.name)
            dept_decision[d.id] = code
            if member_count[d.id] > 0:
                tag = code or "(未匹配-手动)"
                print(f"  {d.name:30} {member_count[d.id]:3}人 -> {tag}")

        # ---- per-user resolution ----
        plan = {}        # user_id -> target role_code
        unmatched = []
        for u in users:
            codes = [c for c in (role_code_by_id.get(ur.role_id) for ur in user_roles[u.id]) if c]
            if "admin" in codes:
                continue  # never touch admins
            best = (None, 9999)
            for did in user_depts.get(u.id, []):
                name = dept_by_id[did].name if did in dept_by_id else ""
                code, idx, _ = role_for_dept_name(name)
                if code and idx < best[1]:
                    best = (code, idx)
            target = best[0]
            if target and u.id in leader_ids:
                target = MANAGER_VARIANT.get(target, target)
            if not target:
                unmatched.append(u)
                continue
            plan[u.id] = target

        print("\n=== 角色分配统计 ===")
        for code, n in Counter(plan.values()).most_common():
            exists = "" if code in role_id_by_code else "  !! 角色不存在，请先跑 seed_function_roles --apply"
            print(f"  {code:20} {n:4} 人{exists}")
        print(f"  (未匹配，需手动) {len(unmatched):4} 人")
        print(f"  (管理员，跳过)   {sum(1 for u in users if 'admin' in [role_code_by_id.get(ur.role_id) for ur in user_roles[u.id]])} 人")

        if unmatched:
            print("\n=== 未匹配用户 (手动指派) ===")
            for u in unmatched[:60]:
                dnames = [dept_by_id[d].name for d in user_depts.get(u.id, []) if d in dept_by_id] or ["(无部门)"]
                print(f"  {u.real_name or u.username:12} 部门: {', '.join(dnames)}")
            if len(unmatched) > 60:
                print(f"  ... 其余 {len(unmatched) - 60} 人")

        if VERBOSE:
            print("\n=== 每个用户的目标角色 ===")
            for u in users:
                if u.id in plan:
                    print(f"  {u.real_name or u.username:12} -> {plan[u.id]}")

        if not APPLY:
            print("\n(dry-run) 未写入。确认无误后加 --apply 执行。")
            return

        # ---- apply ----
        added = replaced = 0
        for uid, code in plan.items():
            rid = role_id_by_code.get(code)
            if not rid:
                continue  # role missing; skip
            have_ids = {ur.role_id for ur in user_roles[uid]}
            if rid not in have_ids:
                db.add(UserRole(id=generate_uuid(), tenant_id=TENANT_ID, user_id=uid, role_id=rid))
                added += 1
            if REPLACE_LEGACY:
                for ur in user_roles[uid]:
                    c = role_code_by_id.get(ur.role_id)
                    if c and c != "admin" and c not in FUNCTION_CODES:
                        await db.delete(ur); replaced += 1
        await db.commit()
        print(f"\n✓ committed. 新增角色绑定 {added} 条" + (f"，移除遗留角色 {replaced} 条" if REPLACE_LEGACY else ""))

        # invalidate the 5-min permission cache so changes take effect without waiting
        try:
            from app.common.cache import cache_delete_pattern
            await cache_delete_pattern(f"user_roles:{TENANT_ID}:*")
            print("✓ 已刷新角色权限缓存。")
        except Exception as e:  # noqa: BLE001
            print(f"(缓存未刷新: {e}; 用户重新登录或最多 5 分钟后生效)")


if __name__ == "__main__":
    asyncio.run(main())
