"""部门 → 角色 自动分配引擎(additive-only)。

规则表 ``dept_role_rules`` 定义「某部门(可含子部门)的成员自动获得某角色」。
在三处触发点调用本模块，把规则落到用户身上：
  - 新建用户 / 编辑用户改部门  (organization.service)
  - 钉钉通讯录同步            (dingtalk_sync.sync_users)
  - 管理员「立即应用到存量用户」按钮

核心原则(与产品决策一致)：
  * 仅新增，绝不删除——只补上缺失的角色，从不移除已有角色。
    因此对同一用户重复调用是幂等的，也不会覆盖管理员手工升的角色(如 sales_manager)。
  * include_children=True 时子部门成员也命中，按 Department.path 前缀匹配。
  * role_id 直接来自本租户 Role 行，天然租户隔离。

调用方负责事务边界：默认 ``commit=True`` 自行提交；批量场景可传 ``commit=False``
在外层统一提交。命中变更的用户会被失效权限/角色缓存(issue #49)。
"""
from __future__ import annotations

import logging

from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid, utcnow
from app.domains.auth.models import UserRole, Role
from app.domains.organization.models import Department, UserDepartment, DeptRoleRule

logger = logging.getLogger("spt_crm.dept_role_auto")

# 分批处理用户，避免 IN(...) 及批量 INSERT 触碰 asyncpg 的 32767 绑定参数上限
# (大租户「立即应用到存量用户」可能有上万用户)。
_USER_CHUNK = 1000


def _rule_matches(user_dept_ids: set[str], user_dept_paths: list[str],
                  rule_dept_id: str, rule_dept_path: str | None,
                  include_children: bool) -> bool:
    """用户当前部门是否命中一条规则。

    直接命中：用户在规则部门下(dept_id 相等)。
    子部门命中：include_children 且用户某部门的物化路径以规则部门路径为前缀。
    """
    if rule_dept_id in user_dept_ids:
        return True
    if include_children and rule_dept_path:
        # 只有像 "/销售中心/" 这样的合法路径才做前缀匹配，空串会误命中全部
        prefix = rule_dept_path if rule_dept_path.endswith("/") else rule_dept_path + "/"
        return any(p and p.startswith(prefix) for p in user_dept_paths)
    return False


async def _load_rules(db: AsyncSession, tenant_id: str) -> list[tuple[DeptRoleRule, str | None]]:
    """加载本租户启用的规则，附带各规则目标部门的物化路径(供子部门匹配)。"""
    rows = (await db.execute(
        select(DeptRoleRule, Department.path)
        .join(Department, and_(
            Department.id == DeptRoleRule.department_id,
            Department.tenant_id == DeptRoleRule.tenant_id,
        ))
        .where(DeptRoleRule.tenant_id == tenant_id, DeptRoleRule.enabled.is_(True))
    )).all()
    return [(r, path) for (r, path) in rows]


async def _user_depts(db: AsyncSession, tenant_id: str, user_ids: list[str]) -> dict[str, tuple[set[str], list[str]]]:
    """user_id -> (部门id集合, 部门物化路径列表)。"""
    rows = (await db.execute(
        select(UserDepartment.user_id, UserDepartment.department_id, Department.path)
        .join(Department, and_(
            Department.id == UserDepartment.department_id,
            Department.tenant_id == UserDepartment.tenant_id,
        ))
        .where(UserDepartment.tenant_id == tenant_id, UserDepartment.user_id.in_(user_ids))
    )).all()
    out: dict[str, tuple[set[str], list[str]]] = {}
    for uid, did, path in rows:
        ids, paths = out.setdefault(uid, (set(), []))
        ids.add(did)
        if path:
            paths.append(path)
    return out


async def apply_dept_role_rules_bulk(
    db: AsyncSession,
    tenant_id: str,
    user_ids: list[str] | None = None,
    *,
    commit: bool = True,
) -> dict:
    """对一批用户应用部门角色规则(additive)。

    user_ids=None 表示对本租户全部用户执行(「立即应用到存量用户」)。
    返回 {"users_touched": n, "roles_added": m}。
    """
    rules = await _load_rules(db, tenant_id)
    if not rules:
        return {"users_touched": 0, "roles_added": 0}

    if user_ids is None:
        from app.domains.auth.models import User
        user_ids = (await db.execute(
            select(User.id).where(User.tenant_id == tenant_id)
        )).scalars().all()
    user_ids = list(dict.fromkeys(user_ids))
    if not user_ids:
        return {"users_touched": 0, "roles_added": 0}

    touched: set[str] = set()
    added = 0
    # 分批：每批各自加载部门/已有角色并落库，控制 IN(...) 与 INSERT 的参数规模。
    for start in range(0, len(user_ids), _USER_CHUNK):
        batch = user_ids[start:start + _USER_CHUNK]
        added_b, touched_b = await _apply_batch(db, tenant_id, batch, rules)
        added += added_b
        touched |= touched_b

    if added:
        if commit:
            await db.commit()
        else:
            await db.flush()
        from app.domains.auth.service import invalidate_user_auth_cache
        for uid in touched:
            await invalidate_user_auth_cache(uid, tenant_id)

    return {"users_touched": len(touched), "roles_added": added}


async def _apply_batch(
    db: AsyncSession,
    tenant_id: str,
    batch: list[str],
    rules: list[tuple[DeptRoleRule, str | None]],
) -> tuple[int, set[str]]:
    """处理一批用户：计算缺失角色并用 ON CONFLICT DO NOTHING 幂等落库。

    返回 (实际新增行数, 实际新增角色的用户集合)。通过 RETURNING 精确统计——即便
    与并发写入撞上唯一键(uq_user_role)，被跳过的行不会被计入。
    """
    dept_map = await _user_depts(db, tenant_id, batch)
    if not dept_map:
        return 0, set()

    existing_rows = (await db.execute(
        select(UserRole.user_id, UserRole.role_id)
        .where(UserRole.tenant_id == tenant_id, UserRole.user_id.in_(batch))
    )).all()
    have: dict[str, set[str]] = {}
    for uid, rid in existing_rows:
        have.setdefault(uid, set()).add(rid)

    now = utcnow()
    to_insert: list[dict] = []
    for uid in batch:
        dept_ids, dept_paths = dept_map.get(uid, (set(), []))
        if not dept_ids:
            continue
        want_roles: set[str] = set()
        for rule, rule_path in rules:
            if _rule_matches(dept_ids, dept_paths, rule.department_id, rule_path, rule.include_children):
                want_roles.add(rule.role_id)
        for rid in want_roles - have.get(uid, set()):
            to_insert.append({
                "id": generate_uuid(), "tenant_id": tenant_id,
                "user_id": uid, "role_id": rid,
                "created_at": now, "updated_at": now,
            })

    if not to_insert:
        return 0, set()

    stmt = (
        pg_insert(UserRole.__table__)
        .values(to_insert)
        .on_conflict_do_nothing(index_elements=["tenant_id", "user_id", "role_id"])
        .returning(UserRole.__table__.c.user_id)
    )
    inserted_uids = (await db.execute(stmt)).scalars().all()
    return len(inserted_uids), set(inserted_uids)


async def apply_dept_role_rules(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    *,
    commit: bool = True,
) -> list[str]:
    """对单个用户应用部门角色规则(additive)。返回「本次新增」的角色 code 列表(可为空)。"""
    before = set((await db.execute(
        select(UserRole.role_id).where(
            UserRole.tenant_id == tenant_id, UserRole.user_id == user_id)
    )).scalars().all())
    result = await apply_dept_role_rules_bulk(db, tenant_id, [user_id], commit=commit)
    if not result["roles_added"]:
        return []
    after = set((await db.execute(
        select(UserRole.role_id).where(
            UserRole.tenant_id == tenant_id, UserRole.user_id == user_id)
    )).scalars().all())
    added_ids = after - before
    if not added_ids:
        return []
    codes = (await db.execute(
        select(Role.code).where(Role.id.in_(added_ids), Role.tenant_id == tenant_id)
    )).scalars().all()
    return list(codes)
