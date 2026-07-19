"""字段级权限：按角色控制字段的「可见 / 脱敏 / 可编辑」。

规则挂在 FieldDefinition 上（值均为角色 code，空/缺省 = 不限制）：
- visible_roles 非空且用户无交集 → 字段对该用户隐藏（读取时连定义带值一并剔除）；
- unmask_roles 非空且用户无交集 → 字段脱敏（值替换为 MASK_VALUE，定义仍在，标记 masked）；
- edit_roles   非空且用户无交集 → 字段只读（写入时忽略其新值，保留原值）。

三者是递进的：隐藏 > 脱敏 > 只读。被脱敏的字段一律不可编辑 —— 用户看不到真实值，
让他提交等于用 "***" 覆盖真数据。

后端是权威边界：读取剔除/脱敏字段值、写入丢弃不可编辑字段的改动；前端 FormRenderer
另做同样判断以隐藏/只读渲染（UX）。设计态（设计器）不受此约束，管理员始终看全部字段。

脱敏哨兵值复用 app.common.field_mask.MASK_VALUE（"***"），与按权限脱敏的那套保持一致 ——
前端已有若干处按 "***" 做防御性判定，再引入第二种哨兵只会让它们漏判。
"""
from __future__ import annotations

from typing import Any, Iterable

from app.common.field_mask import MASK_VALUE


def _roleset(user_roles: Iterable[str] | None) -> set[str]:
    return set(user_roles or [])


def _is_blank(v: Any) -> bool:
    """与规则引擎 _is_empty 同口径：None/空串/空数组为空，0 与 False 不为空。"""
    return v is None or (isinstance(v, str) and v == "") or (isinstance(v, (list, tuple)) and not v)


def field_visible(fd: dict[str, Any], roles: set[str]) -> bool:
    vr = fd.get("visible_roles")
    if not vr:
        return True
    return bool(roles & set(vr))


def field_masked(fd: dict[str, Any], roles: set[str]) -> bool:
    """该字段对此用户是否应脱敏（可见但只给 "***"）。"""
    ur = fd.get("unmask_roles")
    if not ur:
        return False
    return not (roles & set(ur))


def field_editable(fd: dict[str, Any], roles: set[str]) -> bool:
    if not field_visible(fd, roles):
        return False
    if field_masked(fd, roles):
        return False  # 看不到真实值就不能改，否则提交会把 "***" 写回去
    er = fd.get("edit_roles")
    if not er:
        return True
    return bool(roles & set(er))


def has_any_field_permission(field_defs: list[dict[str, Any]] | None) -> bool:
    """是否有任一字段配置了字段级权限（无则可完全跳过裁剪，零开销）。"""
    for fd in field_defs or []:
        if fd.get("visible_roles") or fd.get("edit_roles") or fd.get("unmask_roles"):
            return True
    return False


def filter_read(
    field_defs: list[dict[str, Any]] | None,
    form_data: dict[str, Any] | None,
    user_roles: Iterable[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """读取时裁剪：隐藏字段连定义带值剔除；脱敏字段值换成 "***" 并标记 masked；
    不可编辑字段标记 readonly=True。"""
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
        if field_masked(fd, roles):
            fid = fd.get("id")
            if fid in data:
                data[fid] = MASK_VALUE
            fd = {**fd, "masked": True}
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


async def validate_entity_custom_fields(db, tenant_id: str, entity_type: str, values: Any, user_roles) -> None:
    """校验业务实体扩展字段的必填(含条件必填)，不通过则抛 BusinessException。

    在业务 service 的 create/update 里紧挨 sanitize_entity_write 调用。此前扩展字段的
    required 前后端都没人校验，红色星号纯装饰；条件必填也可被直接调 API 绕过。
    """
    from app.common.error_codes import VALIDATION_ERROR
    from app.common.exceptions import BusinessException
    from app.domains.lowcode.rule_engine import validate_required_with_rules
    from app.domains.lowcode.service import get_entity_fields, get_entity_schema, role_field_permissions

    schema = await get_entity_schema(db, tenant_id, entity_type)
    # 只校验扩展字段：原生字段的覆盖项也存在同一个列表里，但它们的值在业务列上、
    # 不在 custom_fields_json 里，混进来会变成「明明填了该原生字段却报它必填」。
    defs = await get_entity_fields(db, tenant_id, entity_type)
    if not defs:
        return
    err = validate_required_with_rules(
        defs, values if isinstance(values, dict) else {},
        schema["rule_definitions"], role_field_permissions(defs, user_roles),
    )
    if err:
        raise BusinessException(code=VALIDATION_ERROR, message=err)


async def enforce_native_field_policy(
    db, tenant_id: str, entity_type: str, payload: dict, prior: Any, user_roles,
    *, required_scope: str = "all",
) -> dict:
    """对业务实体的「原生字段」施加租户配置的字段策略（后端权威边界）。

    做两件事，与扩展字段那一套完全同源（同一份 schema、同一个规则引擎）：
    1. 只读/隐藏的原生字段丢弃用户新值，保留原值（新建时直接移除）；
    2. 必填（含条件必填）不满足则抛 BusinessException，且跳过被规则隐藏的字段。

    规则条件在「原生值 + 扩展值」的合集上求值，因此显隐可以跨两类字段互相引用。
    prior 为业务对象(更新时)或 None(新建时)。返回处理后的 payload（原地修改并返回）。

    required_scope:
      "all"     —— 校验全部原生必填字段（新建用）。
      "payload" —— 只校验本次请求携带的字段（更新用）。表单编辑会提交全部字段，照常拦；
                   而批量改派/废弃这类只带一两个字段的局部更新，不会因历史数据缺少某个
                   「后来才被设为必填」的字段而整批失败。
    """
    from app.common.error_codes import VALIDATION_ERROR
    from app.common.exceptions import BusinessException
    from app.domains.lowcode.native_field_catalog import has_native_catalog
    from app.domains.lowcode.rule_engine import compute_field_states
    from app.domains.lowcode.service import get_entity_form_schema, role_field_permissions

    if not has_native_catalog(entity_type):
        return payload

    schema = await get_entity_form_schema(db, tenant_id, entity_type)
    native_defs = schema["native_fields"]
    all_defs = native_defs + schema["field_definitions"]
    rules = schema["rule_definitions"]

    # 用户提交后的原生值（未提交的键回落到原值），叠加扩展值，作为规则求值输入
    native_values: dict[str, Any] = {}
    for fd in native_defs:
        fid = fd.get("id")
        native_values[fid] = payload[fid] if fid in payload else getattr(prior, fid, None)
    custom_values = payload.get("custom_fields_json")
    if not isinstance(custom_values, dict):
        custom_values = getattr(prior, "custom_fields_json", None) or {}
    merged = {**native_values, **custom_values}

    perms = role_field_permissions(all_defs, user_roles)
    states = compute_field_states(all_defs, merged, rules, perms)

    stripped = False
    for fd in native_defs:
        fid = fd.get("id")
        st = states.get(fid) or {}
        if st.get("visible", True) and not st.get("readonly", False):
            continue
        if fid not in payload:
            continue
        if prior is not None:
            payload[fid] = getattr(prior, fid, None)
        else:
            payload.pop(fid, None)
        native_values[fid] = payload.get(fid)
        stripped = True

    # 裁剪确实改了值时才重算状态（裁剪可能翻转条件判定）；绝大多数请求没有任何字段被裁，
    # 此时直接复用首次结果，省掉一整轮不动点迭代。
    final_values = {**native_values, **custom_values} if stripped else merged
    final_states = compute_field_states(all_defs, final_values, rules, perms) if stripped else states
    for fd in native_defs:
        fid = fd.get("id")
        if fd.get("form_editable") is False:
            continue  # 表单上没有该输入项（系统/专用流程写入），配必填只会造成无法保存
        if required_scope != "all" and fid not in payload:
            continue
        st = final_states.get(fid) or {}
        if not st.get("visible", True):
            continue  # 被规则隐藏的字段不报必填（否则用户看不到该字段却无法保存）
        if st.get("masked"):
            continue  # 同理：看不到明文就无法填写，脱敏+必填会让记录永远存不下去
        if st.get("required") and _is_blank(final_values.get(fid)):
            raise BusinessException(code=VALIDATION_ERROR, message=f"「{fd.get('label')}」为必填项")
    return payload


async def sanitize_entity_write(db, tenant_id: str, entity_type: str, incoming: Any, prior: Any, user_roles) -> Any:
    """丢弃用户对不可编辑/隐藏扩展字段的写入，保留原值（写入路径，后端权威边界）。"""
    if incoming is None or not isinstance(incoming, dict):
        return incoming
    defs = await _entity_field_defs(db, tenant_id, entity_type)
    if not has_any_field_permission(defs):
        return incoming
    return sanitize_write(incoming, prior if isinstance(prior, dict) else None, defs, user_roles)


async def entity_field_restrictions(db, tenant_id: str, entity_type: str, user_roles) -> dict[str, str]:
    """返回 {原生字段 id: "hidden" | "masked"}，仅含对该用户受限的字段。

    给「不走 dict 序列化」的路径用 —— 典型是 Excel 导出：它直接从模型对象取属性拼行，
    没有可供 strip_entity_dicts 就地修改的 dict。导出若不裁剪，就是一条绕过列表/详情
    脱敏的后门。无任何配置时返回空 dict，调用方零开销。
    """
    from app.domains.lowcode.native_field_catalog import has_native_catalog
    if not has_native_catalog(entity_type):
        return {}
    from app.domains.lowcode.service import get_entity_form_schema
    native_defs = (await get_entity_form_schema(db, tenant_id, entity_type))["native_fields"]
    if not has_any_field_permission(native_defs):
        return {}
    roles = _roleset(user_roles)
    out: dict[str, str] = {}
    for fd in native_defs:
        if not field_visible(fd, roles):
            out[fd.get("id")] = "hidden"
        elif field_masked(fd, roles):
            out[fd.get("id")] = "masked"
    return out


async def ok_entity(db, tenant_id: str, entity_type: str, d: dict, user_roles):
    """裁剪单条实体 dict 后包成标准响应 —— 给「写」端点用（create/update/submit/...）。

    写响应同样会带出实体全量字段，若不裁剪，被隐藏/脱敏的字段就会经写响应漏回前端：
    用户改个备注，响应里就把他无权查看的合同金额一并送回去了。
    与读取路径共用 strip_entity_dicts，重复裁剪是幂等的，可放心叠加。
    """
    from app.common.schemas import ok
    await strip_entity_dicts(db, tenant_id, entity_type, [d], user_roles)
    return ok(d)


def export_cell(restrictions: dict[str, str], field_id: str, value):
    """按字段策略裁剪一个导出单元格：隐藏 → 空串，脱敏 → "***"，否则原值。"""
    r = restrictions.get(field_id)
    if r == "hidden":
        return ""
    if r == "masked":
        return MASK_VALUE
    return value


async def strip_entity_dicts(db, tenant_id: str, entity_type: str, dicts, user_roles, key: str = "custom_fields_json"):
    """读取路径的统一强制点：就地按角色裁剪一批已序列化的实体 dict。

    同时覆盖两类字段：
    - 扩展字段（嵌在 `key` 指向的子 dict 里）；
    - 原生字段（dict 的顶层键，需该实体已在 native_field_catalog 中登记）。

    两类字段的动作一致：隐藏 → 删除该键；脱敏 → 值替换为 "***"。列表 / 详情 / 导出
    共用本函数，每请求只查一次字段定义；无任何权限配置时走快路径原样返回。

    返回入参本身以便链式使用。注意是**就地修改**。
    """
    if not dicts:
        return dicts
    from app.domains.lowcode.native_field_catalog import has_native_catalog

    custom_defs = await _entity_field_defs(db, tenant_id, entity_type)
    native_defs: list[dict[str, Any]] = []
    if has_native_catalog(entity_type):
        from app.domains.lowcode.service import get_entity_form_schema
        native_defs = (await get_entity_form_schema(db, tenant_id, entity_type))["native_fields"]

    has_custom = has_any_field_permission(custom_defs)
    has_native = has_any_field_permission(native_defs)
    if not has_custom and not has_native:
        return dicts

    roles = _roleset(user_roles)
    for d in dicts:
        if has_custom:
            cfj = d.get(key)
            if isinstance(cfj, dict):
                _, d[key] = filter_read(custom_defs, cfj, roles)
        if has_native:
            for fd in native_defs:
                # companions = 该字段的派生显示键(owner_id → owner_name)。列表页渲染的
                # 往往正是派生键，只裁主字段等于脱敏毫无效果，故一并处理。
                keys = [fd.get("id"), *(fd.get("companions") or [])]
                if not field_visible(fd, roles):
                    for k in keys:
                        d.pop(k, None)
                elif field_masked(fd, roles):
                    for k in keys:
                        if k in d:
                            d[k] = MASK_VALUE
    return dicts
