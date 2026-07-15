"""扩展平台 — 表单引擎 API。

路由前缀 /api/v1/lc。权限:
- 表单模板设计/管理: form:view / form:manage
- 表单数据填报/查看: form_data:view / form_data:create / form_data:edit / form_data:delete
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions, get_data_scope
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.common.error_codes import VALIDATION_ERROR
from app.domains.lowcode import schemas, service

router = APIRouter(prefix="/api/v1/lc", tags=["扩展平台-表单引擎"])

# 允许配置扩展字段的既有业务实体
ENTITY_TYPES = {"customer", "project", "lead", "contact", "service_ticket", "order", "contract", "quote", "payment"}


# ==================== 模板序列化 ====================

def _tpl_dict(t) -> dict:
    return schemas.FormTemplateOut.model_validate(t).model_dump()


def _ver_dict(v) -> dict:
    return schemas.FormTemplateVersionOut.model_validate(v).model_dump(mode="json")


def _inst_list_dict(i) -> dict:
    return schemas.FormInstanceListItem.model_validate(i).model_dump(mode="json")


# ==================== 表单模板 ====================

@router.get("/form-templates")
async def list_form_templates(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    name: str = Query(None),
    category: str = Query(None),
    published_only: bool = Query(False),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    items, total = await service.list_templates(
        db, tenant_id, pageNo, pageSize, name=name,
        published_only=published_only, category=category,
    )
    return ok({"items": [_tpl_dict(t) for t in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/form-templates")
async def create_form_template(
    body: schemas.FormTemplateCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    tpl = await service.create_template(db, tenant_id, body, user)
    return ok(_tpl_dict(tpl))


@router.get("/form-templates/{template_id}")
async def get_form_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    tpl = await service.get_template(db, tenant_id, template_id)
    return ok(_tpl_dict(tpl))


@router.put("/form-templates/{template_id}")
async def update_form_template(
    template_id: str,
    body: schemas.FormTemplateUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:manage")),
):
    tpl = await service.update_template(db, tenant_id, template_id, body)
    return ok(_tpl_dict(tpl))


@router.delete("/form-templates/{template_id}")
async def delete_form_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:manage")),
):
    await service.delete_template(db, tenant_id, template_id)
    return ok(None)


# ==================== 设计 / 版本 / 发布 ====================

@router.get("/form-templates/{template_id}/design")
async def load_form_design(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    """设计器加载: 返回最新(草稿优先)版本;无版本返回空设计。"""
    await service.get_template(db, tenant_id, template_id)
    version = await service.get_design(db, tenant_id, template_id)
    if not version:
        return ok({"field_definitions": [], "layout_definition": {}, "rule_definitions": []})
    return ok(_ver_dict(version))


@router.post("/form-templates/{template_id}/design")
async def save_form_design(
    template_id: str,
    body: schemas.SaveDesignRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    version = await service.save_design(db, tenant_id, template_id, body, user.get("sub"))
    return ok(_ver_dict(version))


@router.post("/form-templates/{template_id}/publish")
async def publish_form_template(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    version = await service.publish(db, tenant_id, template_id, user.get("sub"))
    return ok(_ver_dict(version))


@router.get("/form-templates/{template_id}/versions")
async def list_form_versions(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form:view")),
):
    versions = await service.get_versions(db, tenant_id, template_id)
    return ok([_ver_dict(v) for v in versions])


@router.get("/form-templates/{template_id}/published-version")
async def get_published_form_version(
    template_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form_data:view")),
):
    """填报页加载已发布 schema。"""
    version = await service.get_published_version(db, tenant_id, template_id)
    return ok(_ver_dict(version))


# ==================== 实体扩展字段(统一自定义字段到表单引擎) ====================

def _check_entity(entity_type: str):
    if entity_type not in ENTITY_TYPES:
        raise BusinessException(code=VALIDATION_ERROR, message=f"不支持的实体类型: {entity_type}")


@router.get("/entity-templates/{entity_type}")
async def get_entity_template(
    entity_type: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    """取(或创建)该业务实体的扩展字段系统模板,返回后前端跳到表单设计器为其设计字段。"""
    _check_entity(entity_type)
    tpl = await service.get_or_create_entity_template(db, tenant_id, entity_type, user)
    return ok(_tpl_dict(tpl))


@router.get("/entity-fields/{entity_type}")
async def get_entity_fields(
    entity_type: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """取该业务实体已发布的扩展字段定义,供业务表单/详情页用 FormRenderer 渲染。"""
    _check_entity(entity_type)
    fields = await service.get_entity_fields(db, tenant_id, entity_type)
    return ok({"field_definitions": fields})


# ==================== 表单实例(数据) ====================

@router.get("/form-instances")
async def list_form_instances(
    template_id: str = Query(...),
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form_data:view")),
    scope: "list[str] | None" = Depends(get_data_scope),
):
    items, total = await service.list_instances(
        db, tenant_id, template_id, pageNo, pageSize,
        keyword=keyword, status=status, owner_ids=scope,
    )
    return ok({"items": [_inst_list_dict(i) for i in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("/form-instances")
async def create_form_instance(
    body: schemas.FormInstanceCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:create")),
):
    inst = await service.create_instance(db, tenant_id, body, user)
    return ok({"id": inst.id, "status": inst.status, "business_no": inst.business_no})


@router.get("/form-instances/{instance_id}")
async def get_form_instance(
    instance_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form_data:view")),
):
    return ok(await service.get_instance(db, tenant_id, instance_id))


@router.put("/form-instances/{instance_id}")
async def update_form_instance(
    instance_id: str,
    body: schemas.FormInstanceUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:edit")),
):
    inst = await service.update_instance(db, tenant_id, instance_id, body, user)
    return ok({"id": inst.id, "status": inst.status})


@router.delete("/form-instances/{instance_id}")
async def delete_form_instance(
    instance_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form_data:delete")),
):
    await service.delete_instance(db, tenant_id, instance_id, user)
    return ok(None)
