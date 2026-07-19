"""扩展平台 — 表单引擎服务(CRM 风格函数式服务)。

移植自 spt-lowcode 表单服务,适配 CRM: 显式 tenant_id、db.commit() 内聚、current_user dict(user["sub"])。
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR, DUPLICATE_ENTRY, BUSINESS_ERROR
from app.database import generate_uuid
from app.domains.lowcode.models import (
    FormInstance, FormTemplate, FormTemplateVersion,
)
from app.domains.lowcode import schemas
from app.domains.lowcode.formula_engine import compute_formula_fields
from app.domains.lowcode.serial_number import generate_serials_for_submit
from app.domains.lowcode.field_permission import filter_read, sanitize_write
from app.domains.lowcode.rule_engine import validate_required_with_rules


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ==================== 模板 ====================

async def create_template(
    db: AsyncSession, tenant_id: str, data: schemas.FormTemplateCreate, user: dict
) -> FormTemplate:
    code = data.code or f"FORM_{generate_uuid()[:8].upper()}"
    existing = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.code == code,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if existing:
        raise BusinessException(code=DUPLICATE_ENTRY, message=f"表单模板编码 {code} 已存在")

    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        name=data.name, code=code, description=data.description,
        category=data.category, icon=data.icon, sort_order=data.sort_order,
        status="draft", current_version=0, created_by=user.get("sub"),
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def install_builtin_template(
    db: AsyncSession, tenant_id: str, key: str, user: dict
) -> FormTemplate:
    """从内置模板库安装一个模板为本租户草稿表单（含字段的 v1 草稿版本），返回新模板。"""
    from app.domains.lowcode.builtin_templates import get_builtin
    bt = get_builtin(key)
    if not bt:
        raise BusinessException(code=NOT_FOUND, message="内置模板不存在")
    # 保证 code 在租户内唯一(uq_lc_form_template_tenant_code),避免极小概率碰撞抛 IntegrityError。
    code = f"BLT_{key.upper()}_{generate_uuid()[:6].upper()}"
    for _ in range(5):
        dup = (await db.execute(select(FormTemplate.id).where(
            FormTemplate.tenant_id == tenant_id, FormTemplate.code == code,
        ).limit(1))).scalar_one_or_none()
        if not dup:
            break
        code = f"BLT_{key.upper()}_{generate_uuid()[:8].upper()}"
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        name=bt["name"], code=code, description=bt.get("description"),
        category=bt.get("category"), icon=bt.get("icon"),
        status="draft", current_version=0, created_by=user.get("sub"),
    )
    db.add(tpl)
    await db.flush()
    version = FormTemplateVersion(
        id=generate_uuid(), tenant_id=tenant_id, template_id=tpl.id,
        version_number=1, field_definitions=bt["field_definitions"],
        layout_definition={}, rule_definitions=bt.get("rule_definitions", []),
        status="draft",
    )
    db.add(version)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def get_template(db: AsyncSession, tenant_id: str, template_id: str) -> FormTemplate:
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not tpl:
        raise BusinessException(code=NOT_FOUND, message="表单模板不存在")
    return tpl


async def list_templates(
    db: AsyncSession, tenant_id: str, page_no: int, page_size: int,
    name: str | None = None, published_only: bool = False,
    category: str | None = None,
) -> tuple[list[FormTemplate], int]:
    # 排除实体扩展字段的系统模板(is_system)：它们只用于定义业务实体表单的扩展字段，
    # 由「字段管理」维护，不应作为独立表单出现在表单中心/被独立填报。
    conds = [FormTemplate.tenant_id == tenant_id, FormTemplate.is_deleted == False,  # noqa: E712
             FormTemplate.is_system == False]  # noqa: E712
    if name:
        conds.append(FormTemplate.name.ilike(f"%{name}%"))
    if category:
        conds.append(FormTemplate.category == category)
    if published_only:
        conds.append(FormTemplate.status == "published")

    total = (await db.execute(
        select(func.count()).select_from(FormTemplate).where(*conds)
    )).scalar_one()
    rows = (await db.execute(
        select(FormTemplate).where(*conds)
        .order_by(FormTemplate.sort_order.asc(), FormTemplate.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


async def update_template(
    db: AsyncSession, tenant_id: str, template_id: str, data: schemas.FormTemplateUpdate
) -> FormTemplate:
    tpl = await get_template(db, tenant_id, template_id)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(tpl, k, v)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def delete_template(db: AsyncSession, tenant_id: str, template_id: str) -> None:
    tpl = await get_template(db, tenant_id, template_id)
    if tpl.is_system:
        raise BusinessException(code=VALIDATION_ERROR, message="系统内置表单不可删除")
    tpl.is_deleted = True
    await db.commit()


# ==================== 版本 / 设计 / 发布 ====================

async def _get_latest_version(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion | None:
    return (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.tenant_id == tenant_id,
            FormTemplateVersion.template_id == template_id,
        ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
    )).scalar_one_or_none()


async def _get_published_version(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion | None:
    return (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.tenant_id == tenant_id,
            FormTemplateVersion.template_id == template_id,
            FormTemplateVersion.status == "published",
        ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
    )).scalar_one_or_none()


async def save_design(
    db: AsyncSession, tenant_id: str, template_id: str,
    data: schemas.SaveDesignRequest, user_id: str,
) -> FormTemplateVersion:
    """保存表单设计: 更新现有草稿版本,或基于最新版本新建草稿。"""
    await get_template(db, tenant_id, template_id)
    latest = await _get_latest_version(db, tenant_id, template_id)

    new_defs = [fd.model_dump() for fd in data.field_definitions]
    rule_defs = [rd.model_dump() for rd in data.rule_definitions]

    if latest and latest.status == "draft":
        latest.field_definitions = new_defs
        latest.layout_definition = data.layout_definition
        latest.rule_definitions = rule_defs
        await db.commit()
        await db.refresh(latest)
        return latest

    next_version = (latest.version_number + 1) if latest else 1
    version = FormTemplateVersion(
        id=generate_uuid(), tenant_id=tenant_id, template_id=template_id,
        version_number=next_version, field_definitions=new_defs,
        layout_definition=data.layout_definition, rule_definitions=rule_defs,
        status="draft",
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def publish(
    db: AsyncSession, tenant_id: str, template_id: str, user_id: str
) -> FormTemplateVersion:
    """发布: 最新草稿版本设为 published,旧 published 设为 deprecated。"""
    tpl = await get_template(db, tenant_id, template_id)
    latest = await _get_latest_version(db, tenant_id, template_id)
    if not latest or latest.status != "draft":
        raise BusinessException(code=BUSINESS_ERROR, message="没有可发布的草稿版本")

    old_published = await _get_published_version(db, tenant_id, template_id)
    if old_published:
        old_published.status = "deprecated"

    latest.status = "published"
    latest.published_at = _now()
    latest.published_by = user_id
    tpl.status = "published"
    tpl.current_version = latest.version_number
    await db.commit()
    await db.refresh(latest)
    # 实体扩展字段模板发布后，清高级搜索的字段定义缓存，使新字段立即可筛选/显示。
    if tpl.is_system and tpl.entity_type:
        from app.common.search import invalidate_custom_fields
        invalidate_custom_fields(tenant_id, tpl.entity_type)
        invalidate_entity_schema_cache(db, tpl.entity_type)  # 同请求内后续读取取到新版本
    return latest


async def get_versions(
    db: AsyncSession, tenant_id: str, template_id: str
) -> list[FormTemplateVersion]:
    rows = (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.tenant_id == tenant_id,
            FormTemplateVersion.template_id == template_id,
        ).order_by(FormTemplateVersion.version_number.desc())
    )).scalars().all()
    return list(rows)


async def get_published_version(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion:
    v = await _get_published_version(db, tenant_id, template_id)
    if not v:
        raise BusinessException(code=NOT_FOUND, message="该模板尚未发布")
    return v


async def get_design(
    db: AsyncSession, tenant_id: str, template_id: str
) -> FormTemplateVersion | None:
    """设计器加载: 优先最新草稿,否则最新版本(用于继续编辑)。"""
    return await _get_latest_version(db, tenant_id, template_id)


# ==================== 实体扩展字段(统一自定义字段到表单引擎) ====================
# 每个既有业务实体(customer/lead/order/...)的自定义字段 = 一张系统表单模板(is_system, entity_type),
# 用同一套表单设计器设计、同一套 FormRenderer 渲染,值仍存业务表的 custom_fields_json。

async def get_or_create_entity_template(
    db: AsyncSession, tenant_id: str, entity_type: str, user: dict
) -> FormTemplate:
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.entity_type == entity_type,
            FormTemplate.is_system == True,  # noqa: E712
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if tpl:
        return tpl
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=tenant_id,
        name=f"{entity_type} 扩展字段", code=f"__entity_{entity_type}",
        status="draft", current_version=0, is_system=True, entity_type=entity_type,
        created_by=user.get("sub"),
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def get_entity_schema(db: AsyncSession, tenant_id: str, entity_type: str) -> dict:
    """该实体已发布版本里「原样存下」的字段定义 + 规则；未设计则均为空。

    field_definitions 里混有两类条目：扩展字段，以及原生字段的租户覆盖项(native=True)。
    多数调用方要的是前者，请走 get_entity_fields()；要完整表单 schema 走 get_entity_form_schema()。

    规则(rule_definitions)必须与字段一起返回：条件显隐/条件必填/条件只读都靠它，
    早前只返回 field_definitions，导致设计器里配好的规则在业务页面上一条都不生效。

    结果按 session 缓存：一次写入会经 sanitize / validate / enforce 多条路径反复取同一份
    schema，不缓存的话每个请求要多打好几轮 template+version 查询。session 生命周期 = 请求
    生命周期，且本函数只读已发布版本，因此请求内复用是安全的；设计器发布走的是另一个
    session，不会读到过期缓存。
    """
    cache = db.info.setdefault("_lc_entity_schema", {})
    if entity_type in cache:
        return cache[entity_type]

    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.entity_type == entity_type,
            FormTemplate.is_system == True,  # noqa: E712
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    ver = await _get_published_version(db, tenant_id, tpl.id) if tpl else None
    result = {
        "field_definitions": (ver.field_definitions or []) if ver else [],
        "rule_definitions": (ver.rule_definitions or []) if ver else [],
    }
    cache[entity_type] = result
    return result


def invalidate_entity_schema_cache(db: AsyncSession, entity_type: str | None = None) -> None:
    """发布/保存设计后清掉本 session 的 schema 缓存，避免同一请求内读到旧版本。"""
    cache = db.info.get("_lc_entity_schema")
    if not cache:
        return
    if entity_type is None:
        cache.clear()
    else:
        cache.pop(entity_type, None)


async def get_entity_fields(db: AsyncSession, tenant_id: str, entity_type: str) -> list[dict]:
    """只要「扩展」字段定义的便捷入口(字段级权限裁剪、高级搜索列构建等场景用)。

    刻意剔除原生字段(及其覆盖项)：这两处都按字段 id 去 custom_fields_json 里取值，混入
    原生字段会造出指向不存在 JSON 键的 cf_* 搜索列。
    """
    stored = (await get_entity_schema(db, tenant_id, entity_type))["field_definitions"]
    return [fd for fd in stored if not (isinstance(fd, dict) and fd.get("native"))]


async def get_entity_form_schema(db: AsyncSession, tenant_id: str, entity_type: str) -> dict:
    """业务表单渲染/校验用的完整 schema：原生字段 + 扩展字段 + 规则。

    原生字段由 native_field_catalog 重建后叠加租户覆盖项，因此 id/type 永远可信；
    扩展字段原样取用。规则可同时引用两类字段（跨原生/扩展的条件显隐正是靠这一点）。
    """
    from app.domains.lowcode.native_field_catalog import get_system_rules, merge_native_overrides

    schema = await get_entity_schema(db, tenant_id, entity_type)
    stored = schema["field_definitions"]
    native = merge_native_overrides(entity_type, stored)
    custom = [fd for fd in stored if not (isinstance(fd, dict) and fd.get("native"))]
    return {
        "native_fields": native,
        "field_definitions": custom,
        # 内置规则排在前面：表达「该字段仅在特定条件下适用」的业务事实，租户规则可在其后叠加
        "rule_definitions": get_system_rules(entity_type) + schema["rule_definitions"],
    }


# ==================== 校验 ====================

def _is_empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def role_field_permissions(field_defs: list[dict], user_roles) -> list[dict]:
    """由 visible_roles/unmask_roles/edit_roles + 当前用户角色推导规则引擎可用的字段权限。

    与前端 FormRenderer.deriveRolePerms 同口径：空/缺省 = 不限制；隐藏 > 脱敏 > 只读。
    """
    from app.domains.lowcode.field_permission import SYSTEM_ROLE
    roles = set(user_roles or [])
    if SYSTEM_ROLE in roles:
        return []  # 系统主体：无用户角色可评，不施加任何字段级限制
    out: list[dict] = []
    for fd in field_defs or []:
        vr = fd.get("visible_roles")
        if vr and not (roles & set(vr)):
            out.append({"fieldId": fd.get("id"), "access": "hidden"})
            continue
        ur = fd.get("unmask_roles")
        if ur and not (roles & set(ur)):
            # 脱敏即隐含只读：看不到明文的人不该覆盖真实值
            out.append({"fieldId": fd.get("id"), "access": "masked"})
            continue
        er = fd.get("edit_roles")
        if er and not (roles & set(er)):
            out.append({"fieldId": fd.get("id"), "access": "readonly"})
    return out


def validate_required(
    field_defs: list[dict], form_data: dict,
    rules: list[dict] | None = None, permissions: list[dict] | None = None,
) -> str | None:
    """服务端必填校验(顶层字段 + 明细子表必填列)。返回首个错误提示或 None。

    传入 rules 后会先算显隐/条件必填再校验：既让条件必填无法被绕过，也避免「字段被规则
    隐藏、前端不校验、后端仍拦」的死锁。语义与前端 RuleEngine 一致（见 rule_engine.py）。
    """
    return validate_required_with_rules(field_defs, form_data, rules, permissions)


def _extract_amount(form_data: dict, field_defs: list[dict]) -> Decimal | None:
    for fd in field_defs or []:
        if fd.get("type") == "amount" and fd.get("is_indexed"):
            value = form_data.get(fd.get("id"))
            if value is not None:
                try:
                    return Decimal(str(value))
                except (InvalidOperation, ValueError, TypeError):
                    pass
    return None


# ==================== 实例(填报) ====================

async def create_instance(
    db: AsyncSession, tenant_id: str, data: schemas.FormInstanceCreate, user: dict
) -> FormInstance:
    tpl = await get_template(db, tenant_id, data.template_id)
    if tpl.is_system:
        # 实体扩展字段模板只用于业务实体表单的扩展字段，不能作为独立表单填报(否则产生孤立数据)。
        raise BusinessException(code=BUSINESS_ERROR, message="实体扩展字段模板仅用于业务表单，不能独立填报")
    published = await _get_published_version(db, tenant_id, data.template_id)
    if not published:
        raise BusinessException(code=VALIDATION_ERROR, message="该表单模板尚未发布，无法填报")

    field_defs = published.field_definitions or []
    user_name = user.get("real_name") or user.get("username") or ""
    # 字段级权限：丢弃用户对不可编辑/隐藏字段的写入（后端权威边界）
    raw = sanitize_write(data.form_data, None, field_defs, user.get("roles"))
    form_data = compute_formula_fields(dict(raw or {}), field_defs, user_name)

    if not data.as_draft:
        err = validate_required(field_defs, form_data, published.rule_definitions or [],
                                role_field_permissions(field_defs, user.get("roles")))
        if err:
            raise BusinessException(code=VALIDATION_ERROR, message=err)
        form_data = await generate_serials_for_submit(db, tenant_id, data.template_id, field_defs, form_data)

    inst = FormInstance(
        id=generate_uuid(), tenant_id=tenant_id,
        template_id=data.template_id, template_version_id=published.id,
        title=data.title, remark=data.remark,
        status="draft" if data.as_draft else "submitted",
        initiator_id=user.get("sub"), initiator_dept_id=user.get("dept_id"),
        amount=_extract_amount(form_data, field_defs),
        form_data=form_data, field_definitions=field_defs,
        created_by=user.get("sub"),
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)

    # 表单绑定了已发布流程 → 提交即起审批(草稿不触发)。流程状态回写到实例(running/completed/rejected)。
    if not data.as_draft:
        from app.domains.lowcode import workflow_service as wsvc
        pinst = await wsvc.maybe_start_for_form(db, tenant_id, data.template_id, inst, user, form_data)
        if pinst is not None:
            inst.status = pinst.status
            await db.commit()
            await db.refresh(inst)
    return inst


async def get_instance(db: AsyncSession, tenant_id: str, instance_id: str, user: dict | None = None) -> dict:
    inst = (await db.execute(
        select(FormInstance).where(
            FormInstance.id == instance_id,
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="表单数据不存在")

    field_defs = inst.field_definitions or []
    rule_defs: list = []
    version = await db.get(FormTemplateVersion, inst.template_version_id)
    if not version:
        version = await _get_published_version(db, tenant_id, inst.template_id)
    if version:
        if not field_defs:
            field_defs = version.field_definitions or []
        rule_defs = version.rule_definitions or []

    out = schemas.FormInstanceOut.model_validate(inst).model_dump()
    # 字段级权限：按查看者角色剔除隐藏字段(定义+值)，不可编辑字段标记 readonly
    field_defs, out["form_data"] = filter_read(field_defs, out.get("form_data"), (user or {}).get("roles"))
    out["field_definitions"] = field_defs
    out["rule_definitions"] = rule_defs
    return out


async def list_instances(
    db: AsyncSession, tenant_id: str, template_id: str,
    page_no: int, page_size: int,
    keyword: str | None = None, status: str | None = None,
    owner_ids: list[str] | None = None,
) -> tuple[list[FormInstance], int]:
    conds = [
        FormInstance.tenant_id == tenant_id,
        FormInstance.template_id == template_id,
        FormInstance.is_deleted == False,  # noqa: E712
    ]
    if keyword:
        conds.append(FormInstance.title.ilike(f"%{keyword}%"))
    if status:
        conds.append(FormInstance.status == status)
    if owner_ids is not None:  # 数据范围: 仅可见发起人
        conds.append(FormInstance.initiator_id.in_(owner_ids or ["__none__"]))

    total = (await db.execute(
        select(func.count()).select_from(FormInstance).where(*conds)
    )).scalar_one()
    rows = (await db.execute(
        select(FormInstance).where(*conds)
        .order_by(FormInstance.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(rows), total


async def export_instances(
    db: AsyncSession, tenant_id: str, template_id: str,
    keyword: str | None = None, status: str | None = None,
    owner_ids: list[str] | None = None, limit: int = 10000,
) -> tuple[FormTemplate | None, list[dict], list[FormInstance]]:
    """导出表单数据: 返回(模板, 列定义 field_defs, 数据行)。
    列定义优先取已发布版本,否则最新版本(草稿态也可导出)。"""
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id, FormTemplate.tenant_id == tenant_id,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    ver = await _get_published_version(db, tenant_id, template_id)
    if not ver:
        ver = await _get_latest_version(db, tenant_id, template_id)
    field_defs = (ver.field_definitions if ver else []) or []

    conds = [
        FormInstance.tenant_id == tenant_id,
        FormInstance.template_id == template_id,
        FormInstance.is_deleted == False,  # noqa: E712
    ]
    if keyword:
        conds.append(FormInstance.title.ilike(f"%{keyword}%"))
    if status:
        conds.append(FormInstance.status == status)
    if owner_ids is not None:
        conds.append(FormInstance.initiator_id.in_(owner_ids or ["__none__"]))
    rows = (await db.execute(
        select(FormInstance).where(*conds)
        .order_by(FormInstance.created_at.desc())
        .limit(max(1, min(int(limit or 10000), 50000)))
    )).scalars().all()
    return tpl, field_defs, list(rows)


async def update_instance(
    db: AsyncSession, tenant_id: str, instance_id: str,
    data: schemas.FormInstanceUpdate, user: dict,
) -> FormInstance:
    inst = (await db.execute(
        select(FormInstance).where(
            FormInstance.id == instance_id,
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="表单数据不存在")

    if data.title is not None:
        inst.title = data.title
    if data.remark is not None:
        inst.remark = data.remark
    if data.form_data is not None:
        version = await db.get(FormTemplateVersion, inst.template_version_id)
        field_defs = (version.field_definitions if version else inst.field_definitions) or []
        user_name = user.get("real_name") or user.get("username") or ""
        # 字段级权限：不可编辑字段保留原值，忽略用户改动（后端权威边界）
        raw = sanitize_write(data.form_data, inst.form_data, field_defs, user.get("roles"))
        form_data = compute_formula_fields(dict(raw), field_defs, user_name)
        if inst.status != "draft":
            err = validate_required(field_defs, form_data,
                                    (version.rule_definitions if version else []) or [],
                                    role_field_permissions(field_defs, user.get("roles")))
            if err:
                raise BusinessException(code=VALIDATION_ERROR, message=err)
        inst.form_data = form_data
        inst.amount = _extract_amount(form_data, field_defs)

    await db.commit()
    await db.refresh(inst)
    return inst


async def delete_instance(db: AsyncSession, tenant_id: str, instance_id: str, user: dict) -> None:
    inst = (await db.execute(
        select(FormInstance).where(
            FormInstance.id == instance_id,
            FormInstance.tenant_id == tenant_id,
            FormInstance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not inst:
        raise BusinessException(code=NOT_FOUND, message="表单数据不存在")
    inst.is_deleted = True
    inst.deleted_at = _now()
    inst.deleted_by = user.get("sub")
    await db.commit()
