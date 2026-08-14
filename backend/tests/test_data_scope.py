"""数据范围（角色 data_scope）核心逻辑单测。"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.common.data_scope import scoped_owners, resolve_owner_scope, is_in_scope, managed_department_ids


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


async def test_is_in_scope_lead_managed_department(monkeypatch):
    """线索：department_id 落在负责业务部门内即可见（即使 owner 不是本人）。"""
    lead = SimpleNamespace(
        id="L1", owner_id="other", created_by_id="other",
        department_id="dept-yejin", __tablename__="leads", status="new",
    )
    user = {"sub": "intel1", "roles": ["lead_intel"], "permissions": []}

    async def fake_resolve(*_a, **_k):
        return ["intel1"]  # self scope

    async def fake_managed(*_a, **_k):
        return ["dept-yejin", "dept-yejin-child"]

    monkeypatch.setattr("app.common.data_scope.resolve_owner_scope", fake_resolve)
    monkeypatch.setattr("app.common.data_scope.managed_department_ids", fake_managed)

    assert await is_in_scope(MagicMock(), "t1", user, lead, "lead") is True

    lead_other = SimpleNamespace(
        id="L2", owner_id="other", created_by_id="other",
        department_id="dept-jingxi", __tablename__="leads", status="new",
    )
    assert await is_in_scope(MagicMock(), "t1", user, lead_other, "lead") is False


async def test_managed_department_ids_empty_user():
    assert await managed_department_ids(MagicMock(), "t1", None) == []
    assert await managed_department_ids(MagicMock(), "t1", "") == []
