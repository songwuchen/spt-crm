"""字段级权限：按角色控制表单字段的「可见 / 可编辑」。

规则挂在 FieldDefinition 上（visible_roles / edit_roles，值为角色 code）：
- 空/缺省 = 不限制（所有人可见/可编辑）；
- visible_roles 非空且用户无交集 → 字段对该用户隐藏（读取时连定义带值一并剔除）；
- edit_roles 非空且用户无交集 → 字段只读（写入时忽略其新值，保留原值）。

后端是权威边界：读取剔除隐藏字段值、写入丢弃不可编辑字段的改动；前端 FormRenderer
另做同样判断以隐藏/只读渲染（UX）。设计态（设计器）不受此约束，管理员始终看全部字段。
"""
from __future__ import annotations

from typing import Any, Iterable


def _roleset(user_roles: Iterable[str] | None) -> set[str]:
    return set(user_roles or [])


def field_visible(fd: dict[str, Any], roles: set[str]) -> bool:
    vr = fd.get("visible_roles")
    if not vr:
        return True
    return bool(roles & set(vr))


def field_editable(fd: dict[str, Any], roles: set[str]) -> bool:
    if not field_visible(fd, roles):
        return False
    er = fd.get("edit_roles")
    if not er:
        return True
    return bool(roles & set(er))


def has_any_field_permission(field_defs: list[dict[str, Any]] | None) -> bool:
    """是否有任一字段配置了字段级权限（无则可完全跳过裁剪，零开销）。"""
    for fd in field_defs or []:
        if fd.get("visible_roles") or fd.get("edit_roles"):
            return True
    return False


def filter_read(
    field_defs: list[dict[str, Any]] | None,
    form_data: dict[str, Any] | None,
    user_roles: Iterable[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """读取时裁剪：剔除对该用户隐藏的字段定义与其值；不可编辑字段标记 readonly=True。"""
    defs = field_defs or []
    data = dict(form_data or {})
    if not has_any_field_permission(defs):
        return defs, data
    roles = _roleset(user_roles)
    out_defs: list[dict[str, Any]] = []
    for fd in defs:
        if not field_visible(fd, roles):
            data.pop(fd.get("id"), None)
            continue
        if not field_editable(fd, roles):
            fd = {**fd, "readonly": True}
        out_defs.append(fd)
    return out_defs, data


def sanitize_write(
    incoming: dict[str, Any] | None,
    prior: dict[str, Any] | None,
    field_defs: list[dict[str, Any]] | None,
    user_roles: Iterable[str] | None,
) -> dict[str, Any]:
    """写入时裁剪：不可编辑（含隐藏）字段丢弃用户新值，保留原值（新建时原值为空→移除）。"""
    result = dict(incoming or {})
    defs = field_defs or []
    if not has_any_field_permission(defs):
        return result
    roles = _roleset(user_roles)
    prior = prior or {}
    for fd in defs:
        if field_editable(fd, roles):
            continue
        fid = fd.get("id")
        if fid in prior:
            result[fid] = prior[fid]
        else:
            result.pop(fid, None)
    return result


# ===== 实体扩展字段(custom_fields_json)的字段级权限 =====
# 业务实体(客户/商机/...)的扩展字段值存业务表 custom_fields_json，字段定义取自实体系统模板。
# 下面两个 async 助手在业务读写路径调用；无权限配置时快路径原样返回，接近零开销。

async def _entity_field_defs(db, tenant_id: str, entity_type: str) -> list[dict[str, Any]]:
    from app.domains.lowcode.service import get_entity_fields  # 延迟导入避免循环
    return await get_entity_fields(db, tenant_id, entity_type)


async def sanitize_entity_write(db, tenant_id: str, entity_type: str, incoming: Any, prior: Any, user_roles) -> Any:
    """丢弃用户对不可编辑/隐藏扩展字段的写入，保留原值（写入路径，后端权威边界）。"""
    if incoming is None or not isinstance(incoming, dict):
        return incoming
    defs = await _entity_field_defs(db, tenant_id, entity_type)
    if not has_any_field_permission(defs):
        return incoming
    return sanitize_write(incoming, prior if isinstance(prior, dict) else None, defs, user_roles)


async def strip_entity_dicts(db, tenant_id: str, entity_type: str, dicts, user_roles, key: str = "custom_fields_json"):
    """就地按角色剔除一批已序列化 dict 的隐藏扩展字段值（读取路径；列表/详情共用，
    每请求只查一次字段定义；无权限配置时快路径原样返回）。返回入参本身以便链式使用。"""
    if not dicts:
        return dicts
    defs = await _entity_field_defs(db, tenant_id, entity_type)
    if not has_any_field_permission(defs):
        return dicts
    roles = _roleset(user_roles)
    for d in dicts:
        cfj = d.get(key)
        if isinstance(cfj, dict):
            _, d[key] = filter_read(defs, cfj, roles)
    return dicts
