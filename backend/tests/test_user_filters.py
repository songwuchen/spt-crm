"""Tests for 用户列表的多维筛选 (service.list_users).

重点锁定 code review 找出的三个真实缺陷，它们都不会报错、只会静默返回错误结果：
  1. 部门物化路径为空("" 是 Department.path 的列默认值)时，前缀匹配退化成 '%'，
     按该部门筛选会返回全租户所有有部门的用户；
  2. 部门名里的 LIKE 元字符(_ / %)未转义，会串到兄弟部门；
  3. keyword 未转义，搜 "_" 会命中全部。
"""
from sqlalchemy import delete, select

import app.database as db_module
from app.database import generate_uuid
from app.domains.auth.models import User
from app.domains.organization.models import Department, UserDepartment
from app.domains.organization.service import list_users

TENANT = "00000000-0000-0000-0000-000000000001"
PREFIX = "zztf_"


async def _mkdept(db, name: str, path: str) -> str:
    did = generate_uuid()
    db.add(Department(id=did, tenant_id=TENANT, name=PREFIX + name, path=path, sort_order=0))
    return did


async def _mkuser(db, uname: str, dept_ids: list[str]) -> str:
    uid = generate_uuid()
    db.add(User(
        id=uid, tenant_id=TENANT, username=PREFIX + uname, real_name=PREFIX + uname,
        password_hash="x", is_active=True,
    ))
    for did in dept_ids:
        db.add(UserDepartment(id=generate_uuid(), tenant_id=TENANT, user_id=uid, department_id=did))
    return uid


async def _cleanup(db, user_ids, dept_ids):
    await db.execute(delete(UserDepartment).where(UserDepartment.user_id.in_(user_ids)))
    await db.execute(delete(User).where(User.id.in_(user_ids)))
    await db.execute(delete(Department).where(Department.id.in_(dept_ids)))
    await db.commit()


async def _usernames(db, **kwargs) -> set[str]:
    items, _ = await list_users(db, TENANT, 1, 100, **kwargs)
    return {u.username for u in items if u.username.startswith(PREFIX)}


async def test_empty_dept_path_does_not_match_all_departments(client):
    """path="" 的部门只应返回它自己的成员，绝不能退化成「全部部门」。"""
    async with db_module.async_session_factory() as db:
        broken = await _mkdept(db, "无路径部门", "")          # 列默认值就是 ""
        other = await _mkdept(db, "正常部门", "/zztf_正常部门/")
        u_broken = await _mkuser(db, "in_broken", [broken])
        u_other = await _mkuser(db, "in_other", [other])
        await db.commit()
        try:
            assert await _usernames(db, dept_id=broken) == {PREFIX + "in_broken"}
            assert await _usernames(db, dept_id=other) == {PREFIX + "in_other"}
        finally:
            await _cleanup(db, [u_broken, u_other], [broken, other])


async def test_like_metacharacters_in_dept_name_do_not_leak_siblings(client):
    """"/研发_一部/" 的 _ 不得当成通配符匹配到 "/研发X一部/"。"""
    async with db_module.async_session_factory() as db:
        d_underscore = await _mkdept(db, "研发_一部", "/zztf_研发_一部/")
        d_sibling = await _mkdept(db, "研发X一部", "/zztf_研发X一部/")
        u1 = await _mkuser(db, "u_underscore", [d_underscore])
        u2 = await _mkuser(db, "u_sibling", [d_sibling])
        await db.commit()
        try:
            assert await _usernames(db, dept_id=d_underscore) == {PREFIX + "u_underscore"}
            assert await _usernames(db, dept_id=d_sibling) == {PREFIX + "u_sibling"}
        finally:
            await _cleanup(db, [u1, u2], [d_underscore, d_sibling])


async def test_dept_filter_includes_descendants_but_not_name_prefix_siblings(client):
    """含下级要生效，但 "/A/" 不能把同名前缀的 "/AB/" 也算成下级。"""
    async with db_module.async_session_factory() as db:
        parent = await _mkdept(db, "A", "/zztf_A/")
        child = await _mkdept(db, "A_child", "/zztf_A/zztf_child/")
        lookalike = await _mkdept(db, "AB", "/zztf_AB/")
        u_p = await _mkuser(db, "u_parent", [parent])
        u_c = await _mkuser(db, "u_child", [child])
        u_l = await _mkuser(db, "u_lookalike", [lookalike])
        await db.commit()
        try:
            got = await _usernames(db, dept_id=parent)
            assert got == {PREFIX + "u_parent", PREFIX + "u_child"}, got
            assert await _usernames(db, dept_id=lookalike) == {PREFIX + "u_lookalike"}
        finally:
            await _cleanup(db, [u_p, u_c, u_l], [parent, child, lookalike])


async def test_keyword_wildcards_are_escaped(client):
    """搜 "_" 不应被当成单字符通配符命中全部用户。"""
    async with db_module.async_session_factory() as db:
        u_plain = await _mkuser(db, "alice", [])
        u_under = await _mkuser(db, "bo_b", [])
        await db.commit()
        try:
            # "_" 只应精确命中名字里真的含下划线的那个（zztf_ 前缀本身也含 _，
            # 故用更具体的 "o_b" 作为断言）
            assert await _usernames(db, keyword="o_b") == {PREFIX + "bo_b"}
            # 若未转义，"%" 会匹配任意串 -> 命中全部
            assert await _usernames(db, keyword="alice%") == set()
        finally:
            await _cleanup(db, [u_plain, u_under], [])


async def test_unknown_dept_id_returns_empty_not_everything(client):
    async with db_module.async_session_factory() as db:
        d = await _mkdept(db, "solo", "/zztf_solo/")
        u = await _mkuser(db, "solo_member", [d])
        await db.commit()
        try:
            items, total = await list_users(db, TENANT, 1, 100, dept_id=generate_uuid())
            assert total == 0 and items == []
        finally:
            await _cleanup(db, [u], [d])
