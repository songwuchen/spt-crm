"""字段级权限：按角色控制字段的「可见 / 脱敏 / 可编辑 / 附件下载」。

规则挂在 FieldDefinition 上（值均为角色 code，空/缺省 = 不限制）：
- visible_roles 非空且用户无交集 → 字段对该用户隐藏（读取时连定义带值一并剔除）；
- unmask_roles 非空且用户无交集 → 字段脱敏（值替换为 MASK_VALUE，定义仍在，标记 masked）；
- edit_roles   非空且用户无交集 → 字段只读（写入时忽略其新值，保留原值）；
- download_roles 非空且用户无交集 → file/image 字段读时清空附件 ID（标记 download_denied），
  预览/下载 API 另行强制；本单发起人始终可下载。

前三者是递进的：隐藏 > 脱敏 > 只读。被脱敏的字段一律不可编辑 —— 用户看不到真实值，
让他提交等于用 "***" 覆盖真数据。

后端是权威边界：读取剔除/脱敏字段值、写入丢弃不可编辑字段的改动；前端 FormRenderer
另做同样判断以隐藏/只读渲染（UX）。设计态（设计器）不受此约束，管理员始终看全部字段。

脱敏哨兵值复用 app.common.field_mask.MASK_VALUE（"***"），与按权限脱敏的那套保持一致 ——
前端已有若干处按 "***" 做防御性判定，再引入第二种哨兵只会让它们漏判。
"""
from __future__ import annotations

from typing import Any, Iterable

from app.common.field_mask import MASK_VALUE

_FILE_FIELD_TYPES = frozenset({"file", "image"})

# 「系统主体」哨兵角色：服务端到服务端的调用方（开放平台、后台任务）没有用户角色可评。
#
# 字段级权限是按**登录用户角色**的授权概念。若让这类调用方带着空角色集去跑策略，
# 任何配了 visible_roles / unmask_roles 的字段都会因「无交集」被判为隐藏或脱敏，
# 结果是外部集成提交的值被静默丢弃、接口却返回成功；租户配的必填也会把此前能用的
# 集成直接拒掉。二者都不是字段策略该管的事，故整体豁免。
#
# 注意这不是权限提升：能走到这里的调用方已经过各自的鉴权（如开放平台的 app_key）。
SYSTEM_ROLE = "__system__"


def is_system_principal(user_roles: Iterable[str] | None) -> bool:
    return SYSTEM_ROLE in set(user_roles or [])


def _roleset(user_roles: Iterable[str] | None) -> set[str]:
    return set(user_roles or [])


def _is_blank(v: Any) -> bool:
    """与规则引擎 _is_empty 同口径：None/空串/空数组为空，0 与 False 不为空。"""
    return v is None or (isinstance(v, str) and v == "") or (isinstance(v, (list, tuple)) and not v)


def field_visible(fd: dict[str, Any], roles: set[str]) -> bool:
    if SYSTEM_ROLE in roles:
        return True
    vr = fd.get("visible_roles")
    if not vr:
        return True
    return bool(roles & set(vr))


def field_masked(fd: dict[str, Any], roles: set[str]) -> bool:
    """该字段对此用户是否应脱敏（可见但只给 "***"）。"""
    if SYSTEM_ROLE in roles:
        return False
    ur = fd.get("unmask_roles")
    if not ur:
        return False
    return not (roles & set(ur))


def field_editable(fd: dict[str, Any], roles: set[str]) -> bool:
    if SYSTEM_ROLE in roles:
        return True
    if not field_visible(fd, roles):
        return False
    if field_masked(fd, roles):
        return False  # 看不到真实值就不能改，否则提交会把 "***" 写回去
    er = fd.get("edit_roles")
    if not er:
        return True
    return bool(roles & set(er))


def is_file_field(fd: dict[str, Any]) -> bool:
    return (fd.get("type") or "") in _FILE_FIELD_TYPES


def field_downloadable(
    fd: dict[str, Any], roles: set[str], *, is_creator: bool = False,
) -> bool:
    """file/image 是否允许预览/下载。非附件字段恒为 True。

    download_roles 空/缺省 = 不限制；本单发起人与系统主体始终可下载。
    """
    if not is_file_field(fd):
        return True
    if SYSTEM_ROLE in roles or is_creator:
        return True
    dr = fd.get("download_roles")
    if not dr:
        return True
    return bool(roles & set(dr))


def has_any_field_permission(field_defs: list[dict[str, Any]] | None) -> bool:
    """是否有任一字段配置了字段级权限（无则可完全跳过裁剪，零开销）。"""
    for fd in field_defs or []:
        if (
            fd.get("visible_roles")
            or fd.get("edit_roles")
            or fd.get("unmask_roles")
            or fd.get("download_roles")
        ):
            return True
    return False


def filter_read(
    field_defs: list[dict[str, Any]] | None,
    form_data: dict[str, Any] | None,
    user_roles: Iterable[str] | None,
    *,
    is_creator: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """读取时裁剪：隐藏字段连定义带值剔除；脱敏字段值换成 "***" 并标记 masked；
    不可编辑字段标记 readonly=True；无下载权的附件字段清空值并标记 download_denied。"""
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
        if not field_downloadable(fd, roles, is_creator=is_creator):
            fid = fd.get("id")
            if fid is not None:
                data[fid] = []
            fd = {**fd, "download_denied": True, "readonly": True}
        out_defs.append(fd)
    return out_defs, data


def sanitize_write(
    incoming: dict[str, Any] | None,
    prior: dict[str, Any] | None,
    field_defs: list[dict[str, Any]] | None,
    user_roles: Iterable[str] | None,
    *,
    is_creator: bool = False,
) -> dict[str, Any]:
    """写入时裁剪：不可编辑（含隐藏）字段丢弃用户新值，保留原值（新建时原值为空→移除）。

    无附件下载权者即使字段可编辑，也不得改写 file/image 值（防提交空数组清掉附件）。
    """
    result = dict(incoming or {})
    defs = field_defs or []
    if not has_any_field_permission(defs):
        return result
    roles = _roleset(user_roles)
    prior = prior or {}
    for fd in defs:
        editable = field_editable(fd, roles)
        if editable and (
            not is_file_field(fd)
            or field_downloadable(fd, roles, is_creator=is_creator)
        ):
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


async def validate_entity_custom_fields(
    db, tenant_id: str, entity_type: str, values: Any, user_roles,
    *, context: dict | None = None, skip_required: bool = False,
) -> None:
    """校验业务实体扩展字段的必填(含条件必填)，不通过则抛 BusinessException。

    在业务 service 的 create/update 里紧挨 sanitize_entity_write 调用。此前扩展字段的
    required 前后端都没人校验，红色星号纯装饰；条件必填也可被直接调 API 绕过。

    context: 可选的原生字段值（整单 payload），用于条件规则求值。扩展必填校验仍只针对
    扩展字段定义；若不传 context，依赖原生开关的条件规则会求值失败（规则不生效）。
    skip_required: 存草稿时跳过必填（只保留权限裁剪由 sanitize 负责）。
    """
    from app.common.error_codes import VALIDATION_ERROR
    from app.common.exceptions import BusinessException
    from app.domains.lowcode.rule_engine import validate_required_with_rules
    from app.domains.lowcode.service import get_entity_fields, get_entity_schema, role_field_permissions

    if skip_required or is_system_principal(user_roles):
        return  # 草稿 / 系统主体：不拦必填
    schema = await get_entity_schema(db, tenant_id, entity_type)
    # 只校验扩展字段：原生字段的覆盖项也存在同一个列表里，但它们的值在业务列上、
    # 不在 custom_fields_json 里，混进来会变成「明明填了该原生字段却报它必填」。
    defs = await get_entity_fields(db, tenant_id, entity_type)
    if not defs:
        return
    cf = values if isinstance(values, dict) else {}
    # 条件求值需要原生+扩展合集（对齐 FieldPolicy / enforce_native_field_policy）
    merged = {**(context or {}), **cf}
    err = validate_required_with_rules(
        defs, merged,
        schema["rule_definitions"], role_field_permissions(defs, user_roles),
    )
    if err:
        raise BusinessException(code=VALIDATION_ERROR, message=err)


async def enforce_native_field_policy(
    db, tenant_id: str, entity_type: str, payload: dict, prior: Any, user_roles,
    *, required_scope: str = "all", skip_required: bool = False,
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
    skip_required:
      True —— 只做只读/隐藏裁剪，不拦必填（线索存草稿等）。
    """
    from app.common.error_codes import VALIDATION_ERROR
    from app.common.exceptions import BusinessException
    from app.domains.lowcode.native_field_catalog import has_native_catalog
    from app.domains.lowcode.rule_engine import compute_field_states
    from app.domains.lowcode.service import get_entity_form_schema, role_field_permissions

    if not has_native_catalog(entity_type) or is_system_principal(user_roles):
        # 系统主体豁免：否则外部集成提交的受限字段会被静默丢弃、必填也会拒掉此前可用的调用
        return payload

    schema = await get_entity_form_schema(db, tenant_id, entity_type)
    native_defs = schema["native_fields"]
    all_defs = native_defs + schema["field_definitions"]
    rules = schema["rule_definitions"]

    # 用户提交后的原生值（未提交的键回落到原值），叠加扩展值 + JSON 列摊平，作为规则求值输入
    native_values: dict[str, Any] = {}
    for fd in native_defs:
        fid = fd.get("id")
        storage = fd.get("json_storage")
        if storage:
            blob = payload.get(storage)
            if not isinstance(blob, dict):
                blob = getattr(prior, storage, None) if prior is not None else None
            if not isinstance(blob, dict):
                blob = {}
            native_values[fid] = blob.get(fid)
        else:
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
        storage = fd.get("json_storage")
        if storage:
            blob = payload.get(storage)
            if not isinstance(blob, dict) or fid not in blob:
                continue
            if prior is not None:
                prior_blob = getattr(prior, storage, None) or {}
                if not isinstance(prior_blob, dict):
                    prior_blob = {}
                blob[fid] = prior_blob.get(fid)
            else:
                blob.pop(fid, None)
            payload[storage] = blob
            native_values[fid] = blob.get(fid)
            stripped = True
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
    if skip_required:
        return payload
    for fd in native_defs:
        fid = fd.get("id")
        if fd.get("form_editable") is False:
            continue  # 表单上没有该输入项（系统/专用流程写入），配必填只会造成无法保存
        if prior is None and fd.get("available_on_create") is False:
            continue  # 该字段只在记录建立后才出现（如工单解决方案），新建时无从填写
        # 明细子表走独立 JSON 列 / 业务组件提交，不在本表单 payload 里按字段 id 校验必填
        if fd.get("type") == "detail_table" or fd.get("entity_storage"):
            continue
        storage = fd.get("json_storage")
        in_payload = (
            isinstance(payload.get(storage), dict) and fid in payload[storage]
            if storage else fid in payload
        )
        if required_scope != "all" and not in_payload:
            continue
        st = final_states.get(fid) or {}
        if not st.get("visible", True):
            continue  # 被规则隐藏的字段不报必填（否则用户看不到该字段却无法保存）
        if st.get("masked"):
            continue  # 同理：看不到明文就无法填写，脱敏+必填会让记录永远存不下去
        if st.get("required") and _is_blank(final_values.get(fid)):
            raise BusinessException(code=VALIDATION_ERROR, message=f"「{fd.get('label')}」为必填项")
    return payload


def _detail_row_has_value(row: dict) -> bool:
    return any(v is not None and v != "" for v in row.values())


def _detail_col_visible(col: dict, row: dict) -> bool:
    props = col.get("props") or {}
    show_when = props.get("show_when")
    if not isinstance(show_when, dict):
        return True
    field = show_when.get("field")
    if not field:
        return True
    equals = show_when.get("equals") or []
    val = row.get(field)
    s = "" if val is None else str(val)
    return s in [str(x) for x in equals]


def _validate_detail_table_rows(table_label: str, rows: Any, columns: list[dict]) -> None:
    from app.common.error_codes import VALIDATION_ERROR
    from app.common.exceptions import BusinessException

    if not isinstance(rows, list):
        rows = []
    non_empty = [r for r in rows if isinstance(r, dict) and _detail_row_has_value(r)]
    if not non_empty:
        raise BusinessException(code=VALIDATION_ERROR, message=f"请填写{table_label}")
    for i, row in enumerate(non_empty):
        for col in columns:
            if col.get("type") == "formula":
                continue
            props = col.get("props") or {}
            if props.get("computed"):
                continue
            if col.get("available_on_create") is False or col.get("fill_stage") == "approver":
                continue
            if not col.get("required"):
                continue
            if not _detail_col_visible(col, row):
                continue
            cid = col.get("id")
            if _is_blank(row.get(cid)):
                label = col.get("label") or cid
                raise BusinessException(
                    code=VALIDATION_ERROR,
                    message=f"「{table_label}」第 {i + 1} 行「{label}」为必填项",
                )


async def validate_entity_detail_tables(
    db, tenant_id: str, entity_type: str, payload: dict, user_roles,
    *, skip_required: bool = False,
) -> None:
    """校验业务实体明细子表列必填（key_clauses_json 等 JSON 列）。"""
    from app.domains.lowcode.native_field_catalog import has_native_catalog
    from app.domains.lowcode.service import get_entity_form_schema

    if skip_required or is_system_principal(user_roles):
        return
    if not has_native_catalog(entity_type):
        return
    schema = await get_entity_form_schema(db, tenant_id, entity_type)
    for fd in schema["native_fields"]:
        if fd.get("type") != "detail_table":
            continue
        storage = fd.get("entity_storage")
        if not storage or storage not in payload:
            continue
        rows = payload[storage]
        cols = fd.get("detail_table_columns") or []
        if not cols:
            continue
        _validate_detail_table_rows(fd.get("label") or storage, rows, cols)


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
    if not has_native_catalog(entity_type) or is_system_principal(user_roles):
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
    if not dicts or is_system_principal(user_roles):
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
                storage = fd.get("json_storage")
                keys = [fd.get("id"), *(fd.get("companions") or [])]
                if not field_visible(fd, roles):
                    for k in keys:
                        if storage:
                            blob = d.get(storage)
                            if isinstance(blob, dict):
                                blob.pop(k, None)
                                d[storage] = blob
                        else:
                            d.pop(k, None)
                elif field_masked(fd, roles):
                    for k in keys:
                        if storage:
                            blob = d.get(storage)
                            if isinstance(blob, dict) and k in blob:
                                blob = dict(blob)
                                blob[k] = MASK_VALUE
                                d[storage] = blob
                        elif k in d:
                            d[k] = MASK_VALUE
    return dicts


def iter_attachment_ids_in_value(val: Any) -> list[str]:
    """从 file/image 字段值中收集附件 id。"""
    out: list[str] = []
    if isinstance(val, list):
        for item in val:
            if isinstance(item, dict) and item.get("id"):
                out.append(str(item["id"]))
            elif isinstance(item, str) and item:
                out.append(item)
    elif isinstance(val, dict) and val.get("id"):
        out.append(str(val["id"]))
    elif isinstance(val, str) and val:
        out.append(val)
    return out


def _overlay_download_roles(snapshot: list, published: list) -> list:
    pub_by = {
        f["id"]: f for f in (published or [])
        if isinstance(f, dict) and f.get("id")
    }
    out: list = []
    for f in snapshot or []:
        if not isinstance(f, dict):
            continue
        m = dict(f)
        p = pub_by.get(m.get("id"))
        if p is not None and "download_roles" in p:
            m["download_roles"] = p.get("download_roles")
        out.append(m)
    return out


async def assert_form_field_attachment_download(
    db,
    tenant_id: str,
    attachment_id: str,
    current_user: dict,
) -> None:
    """若附件挂在配置了 download_roles 的低代码 file/image 字段上，强制校验。

    未命中任何受控表单字段时直接放行（仍由 attachment:download / 业务可见性约束）。
    """
    from sqlalchemy import String, cast, select

    from app.common.error_codes import FORBIDDEN
    from app.common.exceptions import BusinessException
    from app.domains.lowcode.models import FormInstance, FormTemplateVersion

    roles = _roleset(current_user.get("roles"))
    if SYSTEM_ROLE in roles:
        return

    uid = current_user.get("sub")
    rows = (await db.execute(
        select(FormInstance).where(
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
            cast(FormInstance.form_data, String).contains(attachment_id),
        ).limit(20)
    )).scalars().all()
    if not rows:
        return

    pub_cache: dict[str, list] = {}

    async def _published_defs(template_id: str) -> list:
        if template_id in pub_cache:
            return pub_cache[template_id]
        ver = (await db.execute(
            select(FormTemplateVersion).where(
                FormTemplateVersion.tenant_id == tenant_id,
                FormTemplateVersion.template_id == template_id,
                FormTemplateVersion.status == "published",
            ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
        )).scalar_one_or_none()
        defs = (ver.field_definitions if ver else None) or []
        pub_cache[template_id] = defs
        return defs

    controlled = False
    allowed = False
    for inst in rows:
        data = inst.form_data or {}
        snap = list(inst.field_definitions or [])
        published = await _published_defs(inst.template_id)
        if published:
            snap = _overlay_download_roles(snap, published) if snap else list(published)
            if not snap:
                snap = list(published)
        is_creator = bool(
            uid and (
                uid == getattr(inst, "created_by", None)
                or uid == getattr(inst, "initiator_id", None)
            )
        )
        for fd in snap:
            if not isinstance(fd, dict) or not is_file_field(fd):
                continue
            fid = fd.get("id")
            if not fid:
                continue
            ids = iter_attachment_ids_in_value(data.get(fid))
            if attachment_id not in ids:
                continue
            if not fd.get("download_roles"):
                continue
            controlled = True
            if field_downloadable(fd, roles, is_creator=is_creator):
                allowed = True
                break
        if allowed:
            break

    if controlled and not allowed:
        raise BusinessException(code=FORBIDDEN, message="无权查看该附件")
