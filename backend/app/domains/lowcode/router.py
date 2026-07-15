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
from app.common.export import build_excel, excel_response
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


@router.get("/builtin-templates")
async def list_builtin_templates(
    _user=Depends(require_permissions("form:manage")),
):
    """模板市场: 列出可一键安装的内置表单模板。"""
    from app.domains.lowcode.builtin_templates import list_builtin
    return ok(list_builtin())


@router.post("/builtin-templates/{key}/install")
async def install_builtin_template(
    key: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permissions("form:manage")),
):
    """从模板市场安装内置模板为本租户草稿表单，返回新模板(可继续设计/发布)。"""
    tpl = await service.install_builtin_template(db, tenant_id, key, user)
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


_INST_STATUS_LABELS = {
    "draft": "草稿", "submitted": "已提交", "running": "审批中",
    "completed": "已通过", "rejected": "已驳回", "withdrawn": "已撤回",
}


def _fmt_export_cell(field_type: str | None, value) -> str:
    """把表单字段值格式化成单元格文本（列表/子表/文件等做可读摘要）。"""
    if value is None or value == "":
        return ""
    if field_type in ("detail_table", "sub_table_data"):
        return f"{len(value)} 行" if isinstance(value, list) else str(value)
    if field_type in ("file", "image"):
        return f"{len(value)} 个文件" if isinstance(value, list) else str(value)
    if field_type == "switch" or isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        return "、".join(
            str(v.get("name") or v.get("label") or v.get("id") or v) if isinstance(v, dict) else str(v)
            for v in value
        )
    if isinstance(value, dict):
        return str(value.get("name") or value.get("label") or value.get("text") or value)
    return str(value)


@router.get("/form-instances/export")
async def export_form_instances(
    template_id: str = Query(...),
    keyword: str = Query(None),
    status: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("form_data:view")),
    scope: "list[str] | None" = Depends(get_data_scope),
):
    """导出当前筛选下的表单数据为 Excel（列＝表单字段，含业务编号/状态/创建时间）。"""
    tpl, field_defs, rows = await service.export_instances(
        db, tenant_id, template_id, keyword=keyword, status=status, owner_ids=scope,
    )
    data_fields = [fd for fd in field_defs if fd.get("id")]
    headers = ["业务编号", "标题", "状态", "创建时间"] + [fd.get("label") or fd.get("id") for fd in data_fields]
    data_rows = []
    for inst in rows:
        fd_data = inst.form_data or {}
        line = [
            inst.business_no or "", inst.title or "",
            _INST_STATUS_LABELS.get(inst.status, inst.status or ""),
            inst.created_at.strftime("%Y-%m-%d %H:%M") if inst.created_at else "",
        ]
        line += [_fmt_export_cell(fd.get("type"), fd_data.get(fd.get("id"))) for fd in data_fields]
        data_rows.append(line)
    sheet = (tpl.name if tpl else "表单数据")[:31]
    buf = build_excel(sheet, headers, data_rows)
    return excel_response(buf, "form_data.xlsx")


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
