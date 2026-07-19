"""系统主体（开放平台等服务端调用方）豁免字段级权限。

回归：_pseudo_user 原本不带 roles，内部 service 又跑按登录用户角色的字段策略 ——
空角色集与任何 visible_roles/unmask_roles 都无交集，于是外部集成提交的受限字段
被静默丢弃（接口仍返回成功），租户配的必填还会把此前可用的集成直接拒掉。
"""
import pytest

from app.domains.lowcode.field_permission import (
    SYSTEM_ROLE,
    field_editable,
    field_masked,
    field_visible,
    is_system_principal,
)
from app.domains.lowcode.service import role_field_permissions

RESTRICTED = {
    "id": "amount", "label": "金额",
    "visible_roles": ["finance"], "unmask_roles": ["finance"], "edit_roles": ["finance"],
}


def test_openapi_pseudo_user_carries_system_role():
    """伪用户必须带 SYSTEM_ROLE，否则策略会当它是「一个没有任何角色的真人」。"""
    from app.domains.openapi.service import _pseudo_user

    class _Ctx:
        app_id, app_key, tenant_id = "app-1", "KEY", "t-1"

    user = _pseudo_user(_Ctx())
    assert is_system_principal(user.get("roles")), "开放平台伪用户丢了系统主体标记"


@pytest.mark.parametrize("roles,visible,masked,editable", [
    ({SYSTEM_ROLE}, True, False, True),   # 系统主体：不受任何限制
    (set(), False, True, False),          # 无角色的真人：受限
    ({"finance"}, True, False, True),     # 有对应角色：不受限
    ({"sales"}, False, True, False),      # 有其他角色：受限
])
def test_field_predicates_exempt_system_principal(roles, visible, masked, editable):
    assert field_visible(RESTRICTED, roles) is visible
    assert field_masked(RESTRICTED, roles) is masked
    assert field_editable(RESTRICTED, roles) is editable


def test_role_permissions_empty_for_system_principal():
    """系统主体不产出任何字段权限项，规则引擎因此不会把字段判为隐藏/脱敏。"""
    assert role_field_permissions([RESTRICTED], [SYSTEM_ROLE]) == []
    # 对照：无角色的真人会拿到 hidden
    assert role_field_permissions([RESTRICTED], [])[0]["access"] == "hidden"


async def test_openapi_create_keeps_restricted_field(client, auth_headers):
    """端到端：租户给字段配了角色限制后，开放平台路径提交的值不得被丢弃。"""
    from app.domains.lowcode.field_permission import enforce_native_field_policy
    from app.database import async_session_factory

    h = auth_headers
    tpl = (await client.get("/api/v1/lc/entity-templates/lead", headers=h)).json()["data"]

    async def publish(defs):
        await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/design", headers=h, json={
            "field_definitions": defs, "layout_definition": {}, "rule_definitions": []})
        await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/publish", headers=h)

    try:
        await publish([{"id": "budget_range", "native": True, "label": "预算范围",
                        "type": "select", "visible_roles": ["finance"]}])
        tenant_id = "00000000-0000-0000-0000-000000000001"
        async with async_session_factory() as db:
            # 系统主体：值保留
            # required_scope="payload" 隔离出「裁剪」行为，避免被 title 等必填字段干扰
            kept = await enforce_native_field_policy(
                db, tenant_id, "lead", {"budget_range": "100-500万"}, None, [SYSTEM_ROLE],
                required_scope="payload")
            assert kept.get("budget_range") == "100-500万", "系统主体的提交值被误丢弃"

            # 对照：无该角色的真人，值被剔除
            dropped = await enforce_native_field_policy(
                db, tenant_id, "lead", {"budget_range": "100-500万"}, None, ["sales"],
                required_scope="payload")
            assert "budget_range" not in dropped
    finally:
        await publish([])
