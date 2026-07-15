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
    conds = [FormTemplate.tenant_id == tenant_id, FormTemplate.is_deleted == False]  # noqa: E712
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


async def get_entity_fields(db: AsyncSession, tenant_id: str, entity_type: str) -> list[dict]:
    """返回该实体已发布的扩展字段定义(供业务表单/详情页渲染);未设计则空。"""
    tpl = (await db.execute(
        select(FormTemplate).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.entity_type == entity_type,
            FormTemplate.is_system == True,  # noqa: E712
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not tpl:
        return []
    ver = await _get_published_version(db, tenant_id, tpl.id)
    return (ver.field_definitions if ver else []) or []


# ==================== 校验 ====================

def _is_empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def validate_required(field_defs: list[dict], form_data: dict) -> str | None:
    """服务端必填校验(顶层字段 + 明细子表必填列)。返回首个错误提示或 None。"""
    for fd in field_defs or []:
        ftype = fd.get("type")
        if ftype in ("formula", "auto_number"):  # 系统生成,免必填
            continue
        label = fd.get("label") or "字段"
        if fd.get("required") and _is_empty(form_data.get(fd.get("id"))):
            return f"「{label}」为必填项"
        if ftype == "detail_table":
            rows = form_data.get(fd.get("id"))
            cols = fd.get("detail_table_columns") or []
            req_cols = [c for c in cols if c.get("required")]
            if isinstance(rows, list) and req_cols:
                for idx, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    for c in req_cols:
                        if _is_empty(row.get(c.get("id"))):
                            return f"「{label}」第 {idx + 1} 行「{c.get('label') or '列'}」为必填项"
    return None


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
    published = await _get_published_version(db, tenant_id, data.template_id)
    if not published:
        raise BusinessException(code=VALIDATION_ERROR, message="该表单模板尚未发布，无法填报")

    field_defs = published.field_definitions or []
    user_name = user.get("real_name") or user.get("username") or ""
    form_data = compute_formula_fields(dict(data.form_data or {}), field_defs, user_name)

    if not data.as_draft:
        err = validate_required(field_defs, form_data)
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


async def get_instance(db: AsyncSession, tenant_id: str, instance_id: str) -> dict:
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
        form_data = compute_formula_fields(dict(data.form_data), field_defs, user_name)
        if inst.status != "draft":
            err = validate_required(field_defs, form_data)
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
