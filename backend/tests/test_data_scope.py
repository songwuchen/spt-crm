"""数据范围（角色 data_scope）核心逻辑单测。"""
from app.common.data_scope import scoped_owners, resolve_owner_scope


def test_scoped_owners_all_scope():
    # scope=None 表示可见全部
    assert scoped_owners(None, None) is None
    # 可见全部时，显式 owner_id 作为普通筛选
    assert scoped_owners("u1", None) == ["u1"]


def test_scoped_owners_restricted():
    scope = ["a", "b", "c"]
    # 无显式筛选 -> 落在范围内
    assert scoped_owners(None, scope) == scope
    # 显式筛选范围内的 owner -> 允许
    assert scoped_owners("a", scope) == ["a"]
    # 显式筛选范围外的 owner -> 越权，返回空（无可见数据），不得绕过
    assert scoped_owners("zzz", scope) == []


async def test_resolve_owner_scope_admin_bypass():
    # 管理员 / data:view_all / * 均不受限（不触库，db 传 None 也安全）
    assert await resolve_owner_scope(None, {"sub": "u1", "roles": ["admin"]}) is None
    assert await resolve_owner_scope(None, {"sub": "u1", "permissions": ["data:view_all"]}) is None
    assert await resolve_owner_scope(None, {"sub": "u1", "permissions": ["*"]}) is None
    assert await resolve_owner_scope(None, {"sub": "u1", "roles": ["super_admin"]}) is None
