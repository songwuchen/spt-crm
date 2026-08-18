"""数据范围（角色 data_scope + 按模块 scope_by_resource）核心逻辑单测。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.common.data_scope import (
    scoped_owners, resolve_owner_scope, is_in_scope, managed_department_ids,
    _effective_scope, normalize_scope_by_resource,
)


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


def test_effective_scope_override():
    assert _effective_scope("dept", {"customer": "all"}, "customer") == "all"
    assert _effective_scope("dept", {"customer": "all"}, "lead") == "dept"
    assert _effective_scope("dept", None, "customer") == "dept"
    assert _effective_scope("self", {"lead": "bogus"}, "lead") == "self"
    assert _effective_scope(None, {}, None) == "self"


def test_normalize_scope_by_resource():
    assert normalize_scope_by_resource({"customer": "all", "lead": "x", 1: "all"}) == {"customer": "all"}
    assert normalize_scope_by_resource({"unknown_mod": "all", "quote": "dept"}) == {"quote": "dept"}
    assert normalize_scope_by_resource(None) == {}


async def test_resolve_owner_scope_admin_bypass():
    # 管理员 / data:view_all / * 均不受限（不触库，db 传 None 也安全）
    assert await resolve_owner_scope(None, {"sub": "u1", "roles": ["admin"]}) is None
    assert await resolve_owner_scope(None, {"sub": "u1", "permissions": ["data:view_all"]}) is None
    assert await resolve_owner_scope(None, {"sub": "u1", "permissions": ["*"]}) is None
    assert await resolve_owner_scope(None, {"sub": "u1", "roles": ["super_admin"]}) is None


async def test_resolve_owner_scope_per_module():
    """同角色默认 dept + customer=all：客户不限，线索仍部门成员。"""
    user = {"sub": "u-mkt", "roles": ["mkt_support"], "permissions": [], "tenant_id": "t1"}
    calls = {"n": 0}

    async def fake_execute(_stmt):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(all=lambda: [("dept", {"customer": "all"})])
        if calls["n"] == 2:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: ["d1"]))
        if calls["n"] == 3:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: ["/d1/"]))
        if calls["n"] == 4:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: ["u-mkt", "u-peer"]))

    db = MagicMock()
    db.execute = AsyncMock(side_effect=fake_execute)

    assert await resolve_owner_scope(db, user, "t1", biz_type="customer") is None

    calls["n"] = 0
    lead_scope = await resolve_owner_scope(db, user, "t1", biz_type="lead")
    assert lead_scope is not None
    assert set(lead_scope) >= {"u-mkt", "u-peer"}


async def test_is_in_scope_lead_managed_department(monkeypatch):
    """线索：department_id 落在负责业务部门内即可见（即使 owner 不是本人）。"""
    lead = SimpleNamespace(
        id="L1", owner_id="other", created_by_id="other",
        department_id="dept-yejin", __tablename__="leads", status="new",
        review_status="approved",
    )
    user = {"sub": "intel1", "roles": ["lead_intel"], "permissions": []}

    async def fake_resolve(*_a, **_k):
        return ["intel1"]  # self scope

    async def fake_managed(*_a, **_k):
        return ["dept-yejin", "dept-yejin-child"]

    monkeypatch.setattr("app.common.data_scope.resolve_owner_scope", fake_resolve)
    monkeypatch.setattr("app.common.data_scope.managed_department_ids", fake_managed)
    monkeypatch.setattr(
        "app.common.data_scope.resolve_module_scope",
        AsyncMock(return_value="self"),
    )

    assert await is_in_scope(MagicMock(), "t1", user, lead, "lead") is True

    lead_other = SimpleNamespace(
        id="L2", owner_id="other", created_by_id="other",
        department_id="dept-jingxi", __tablename__="leads", status="new",
        review_status="approved",
    )
    assert await is_in_scope(MagicMock(), "t1", user, lead_other, "lead") is False


async def test_is_in_scope_lead_draft_private_even_for_all(monkeypatch):
    """草稿仅负责人/创建人/报备人可见；data_scope=all 也不能看别人的草稿。"""
    async def fake_all(*_a, **_k):
        return None  # all

    monkeypatch.setattr("app.common.data_scope.resolve_owner_scope", fake_all)

    other_draft = SimpleNamespace(
        id="D1", owner_id="u-other", created_by_id="u-other", reporter_id="u-other",
        department_id="d1", __tablename__="leads", status="new",
        review_status="draft",
    )
    viewer = {"sub": "u-me", "roles": ["mkt_support"], "permissions": ["data:view_all"]}
    assert await is_in_scope(MagicMock(), "t1", viewer, other_draft, "lead") is False

    mine_as_owner = SimpleNamespace(
        id="D2", owner_id="u-me", created_by_id="u-other", reporter_id="u-other",
        department_id="d1", __tablename__="leads", status="new",
        review_status="draft",
    )
    assert await is_in_scope(MagicMock(), "t1", viewer, mine_as_owner, "lead") is True

    mine_as_creator = SimpleNamespace(
        id="D3", owner_id="u-other", created_by_id="u-me", reporter_id="u-other",
        department_id="d1", __tablename__="leads", status="new",
        review_status="draft",
    )
    assert await is_in_scope(MagicMock(), "t1", viewer, mine_as_creator, "lead") is True

    mine_as_reporter = SimpleNamespace(
        id="D4", owner_id="u-other", created_by_id="u-other", reporter_id="u-me",
        department_id="d1", __tablename__="leads", status="new",
        review_status="draft",
    )
    assert await is_in_scope(MagicMock(), "t1", viewer, mine_as_reporter, "lead") is True

    # 非草稿：all 仍可见
    approved = SimpleNamespace(
        id="A1", owner_id="u-other", created_by_id="u-other", reporter_id="u-other",
        department_id="d1", __tablename__="leads", status="new",
        review_status="approved",
    )
    assert await is_in_scope(MagicMock(), "t1", viewer, approved, "lead") is True


async def test_is_in_scope_lead_reporter_as_salesperson(monkeypatch):
    """报备人=业务员：self 范围下即使不是负责人/创建人也可访问线索（转商机确认）。"""
    lead = SimpleNamespace(
        id="L-rpt", owner_id="u-owner", created_by_id="u-owner",
        reporter_id="u-reporter", department_id=None,
        __tablename__="leads", status="new", review_status="approved",
    )
    user = {"sub": "u-reporter", "roles": ["customer_entry"], "permissions": []}

    async def fake_self(*_a, **_k):
        return ["u-reporter"]

    monkeypatch.setattr("app.common.data_scope.resolve_owner_scope", fake_self)
    monkeypatch.setattr(
        "app.common.data_scope.managed_department_ids",
        AsyncMock(return_value=[]),
    )

    assert await is_in_scope(MagicMock(), "t1", user, lead, "lead") is True

    stranger = {"sub": "u-stranger", "roles": ["customer_entry"], "permissions": []}

    async def fake_stranger(*_a, **_k):
        return ["u-stranger"]

    monkeypatch.setattr("app.common.data_scope.resolve_owner_scope", fake_stranger)
    assert await is_in_scope(MagicMock(), "t1", stranger, lead, "lead") is False


async def test_is_in_scope_lead_dept_uses_form_department_not_owner_sidejob(monkeypatch):
    """部门档以线索表 department_id 为准：负责人兼职本部门不能放大到平级事业部。

    岳毅挂市场支持中心（与精细筛分平级）；张玲玉同时挂市场支持中心+精细筛分。
    所在部门=精细筛分的单，旧逻辑因负责人在岳毅部门而可见，现应不可见。
    """
    user = {"sub": "u-yueyi", "roles": ["mkt_support"], "permissions": []}

    async def fake_resolve(*_a, **_k):
        # 旧口径会把兼职同事算进 owner 集合
        return ["u-yueyi", "u-zhanglingyu"]

    monkeypatch.setattr("app.common.data_scope.resolve_owner_scope", fake_resolve)
    monkeypatch.setattr(
        "app.common.data_scope.managed_department_ids",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.common.data_scope.resolve_module_scope",
        AsyncMock(return_value="dept"),
    )
    monkeypatch.setattr(
        "app.common.data_scope.org_department_subtree_ids",
        AsyncMock(return_value=["dept-mkt", "dept-yejin", "dept-wash", "dept-ops"]),
    )

    jingxi = SimpleNamespace(
        id="L-jx", owner_id="u-zhanglingyu", created_by_id="u-zhanglingyu",
        reporter_id="u-zhanglingyu", department_id="dept-jingxi",
        __tablename__="leads", status="new", review_status="approved",
    )
    assert await is_in_scope(MagicMock(), "t1", user, jingxi, "lead") is False

    own_dept = SimpleNamespace(
        id="L-mkt", owner_id="u-zhanglingyu", created_by_id="u-zhanglingyu",
        reporter_id="u-zhanglingyu", department_id="dept-mkt",
        __tablename__="leads", status="new", review_status="approved",
    )
    assert await is_in_scope(MagicMock(), "t1", user, own_dept, "lead") is True

    mine_even_if_jingxi = SimpleNamespace(
        id="L-mine", owner_id="u-yueyi", created_by_id="u-other",
        reporter_id="u-other", department_id="dept-jingxi",
        __tablename__="leads", status="new", review_status="approved",
    )
    assert await is_in_scope(MagicMock(), "t1", user, mine_even_if_jingxi, "lead") is True


async def test_is_in_scope_lead_self_ignores_org_department_subtree(monkeypatch):
    """self 档（业务员）不因组织部门子树放开同事单据；负责业务部门仍可见。"""
    user = {"sub": "u-sales", "roles": ["customer_entry"], "permissions": []}

    async def fake_self(*_a, **_k):
        return ["u-sales"]

    monkeypatch.setattr("app.common.data_scope.resolve_owner_scope", fake_self)
    monkeypatch.setattr(
        "app.common.data_scope.managed_department_ids",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.common.data_scope.resolve_module_scope",
        AsyncMock(return_value="self"),
    )
    monkeypatch.setattr(
        "app.common.data_scope.org_department_subtree_ids",
        AsyncMock(return_value=["dept-mkt"]),
    )

    peer = SimpleNamespace(
        id="L-peer", owner_id="u-peer", created_by_id="u-peer",
        reporter_id="u-peer", department_id="dept-mkt",
        __tablename__="leads", status="new", review_status="approved",
    )
    assert await is_in_scope(MagicMock(), "t1", user, peer, "lead") is False


async def test_managed_department_ids_empty_user():
    assert await managed_department_ids(MagicMock(), "t1", None) == []
    assert await managed_department_ids(MagicMock(), "t1", "") == []
