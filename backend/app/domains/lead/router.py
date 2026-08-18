from datetime import date

from fastapi import APIRouter, Depends, Query, Header as FastAPIHeader, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, build_excel_multi, excel_response
from app.domains.lead import service
from app.domains.lead.import_excel import (
    LEAD_IMPORT_HEADERS,
    lead_import_guide_rows,
    lead_import_sample_row,
    map_header_row,
    parse_upload_rows,
    row_to_payload,
    rows_for_preview,
)
from app.domains.lowcode.field_permission import ok_entity, strip_entity_dicts

router = APIRouter(prefix="/api/v1/leads", tags=["线索管理"])


def _product_dict(p) -> dict:
    return {
        "id": p.id, "product_name": p.product_name, "product_spec": p.product_spec,
        "quantity": float(p.quantity) if p.quantity is not None else None,
        "remark": p.remark,
    }


def _lead_dict(l, products=None, dept_names=None) -> dict:
    """线索出参的唯一序列化入口（没有 Out schema，改字段请只改这里）。

    dept_names: department_id -> name 的批量映射，由调用方预取以避免逐条查询；
    未传时 department_name 为 None，前端退化为不显示部门名。
    """
    return {
        "id": l.id, "lead_code": l.lead_code, "title": l.title, "company_name": l.company_name,
        "contact_name": l.contact_name, "contact_phone": l.contact_phone,
        "contact_email": l.contact_email, "contact_raw_json": l.contact_raw_json,
        "source": l.source, "source_detail_json": l.source_detail_json,
        "demand_summary": l.demand_summary,
        "industry": l.industry,
        "customer_type": l.customer_type,
        "category": l.category,
        "country_type": l.country_type,
        "country_name": l.country_name,
        "region": l.region,
        "province": l.province,
        "city": l.city,
        "district": l.district,
        "region_code": l.region_code,
        "department_id": l.department_id,
        "department_name": (dept_names or {}).get(l.department_id),
        "budget_range": l.budget_range,
        "reporter_id": getattr(l, "reporter_id", None),
        "reporter_name": getattr(l, "reporter_name", None),
        "reported_at": l.reported_at.isoformat() if getattr(l, "reported_at", None) else None,
        "owner_id": l.owner_id, "owner_name": l.owner_name,
        "created_by_id": l.created_by_id, "created_by_name": l.created_by_name,
        "biz_date": str(l.biz_date) if l.biz_date else None,
        "status": l.status, "score": l.score,
        "review_status": getattr(l, "review_status", "approved"),
        "review_flow_id": getattr(l, "review_flow_id", None),
        "reject_reason": getattr(l, "reject_reason", None),
        "customer_newness": getattr(l, "customer_newness", None),
        "review_opinion": getattr(l, "review_opinion", None),
        "has_internal_conflict": getattr(l, "has_internal_conflict", None),
        "conflict_note": getattr(l, "conflict_note", None),
        "bid_result": getattr(l, "bid_result", None),
        "bid_fail_reason": getattr(l, "bid_fail_reason", None),
        "entrust_status": getattr(l, "entrust_status", None),
        "entrust_issued_at": (
            l.entrust_issued_at.isoformat() if getattr(l, "entrust_issued_at", None) else None
        ),
        "entrust_term": getattr(l, "entrust_term", None),
        "project_activity": getattr(l, "project_activity", None),
        "project_recent": getattr(l, "project_recent", None),
        "follow_progress": getattr(l, "follow_progress", None),
        "site_visit": getattr(l, "site_visit", None),
        "report_project_status": getattr(l, "report_project_status", None),
        "assess_remark": getattr(l, "assess_remark", None),
        "cycle_anchor_at": (
            l.cycle_anchor_at.isoformat() if getattr(l, "cycle_anchor_at", None) else None
        ),
        "reactivation_status": getattr(l, "reactivation_status", None) or "none",
        "reactivation_notified_at": (
            l.reactivation_notified_at.isoformat()
            if getattr(l, "reactivation_notified_at", None) else None
        ),
        "reactivation_round": getattr(l, "reactivation_round", None) or 0,
        "converted_customer_id": l.converted_customer_id,
        "remark": l.remark,
        # 扩展字段值必须回传：strip_entity_dicts 依赖它做字段级权限裁剪，前端编辑表单也据此
        # 回填，缺失会导致保存时以空对象覆盖掉已存值。
        "custom_fields_json": l.custom_fields_json or {},
        "products": [_product_dict(p) for p in products] if products is not None else [],
        "created_at": l.created_at.isoformat() if l.created_at else "",
        "updated_at": l.updated_at.isoformat() if l.updated_at else "",
    }


@router.get("")
async def list_leads(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    owner_id: str = Query(None),
    customer_type: str = Query(None),
    category: str = Query(None),
    country_type: str = Query(None),
    province: str = Query(None),
    department_id: str = Query(None),
    industry: str = Query(None),
    company_name: str = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    date_field: str = Query(None, description="日期区间筛选字段：created_at(默认) / biz_date"),
    filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
    sort_by: str = Query(None),
    sort_order: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    # 数据范围「本人」= 负责人/创建人/报备人(业务员)/共享给本人；「部门」= 部门子树成员；「全部」= 不限。
    items, total = await service.list_leads(
        db, tenant_id, pageNo, pageSize, keyword, status, owner_id,
        customer_type=customer_type, category=category, country_type=country_type,
        province=province, department_id=department_id, industry=industry,
        company_name=company_name, start_date=start_date, end_date=end_date,
        date_field=date_field, current_user=_user,
        adv_filter=filter, sort_by=sort_by, sort_order=sort_order,
    )
    dept_names = await _lead_department_names(db, tenant_id, items)  # 一次查询，避免逐条取部门名
    dicts = [_lead_dict(l, dept_names=dept_names) for l in items]
    await strip_entity_dicts(db, tenant_id, "lead", dicts, _user.get("roles"))  # 字段级权限：读取剔除隐藏扩展字段
    return ok({"items": dicts, "total": total, "pageNo": pageNo, "pageSize": pageSize})


async def _lead_department_names(db: AsyncSession, tenant_id: str, items) -> dict:
    """批量取 department_id -> name，供导出回填部门名。"""
    from sqlalchemy import select
    from app.domains.organization.models import Department
    ids = {l.department_id for l in items if l.department_id}
    if not ids:
        return {}
    rows = (await db.execute(select(Department.id, Department.name).where(
        Department.tenant_id == tenant_id, Department.id.in_(ids)))).all()
    return {did: name for did, name in rows}


async def _lead_products_text(db: AsyncSession, tenant_id: str, items) -> dict:
    """批量取各线索的产品明细，拼成一段可读文本供导出（一条线索可有多个产品）。"""
    from sqlalchemy import select
    from app.domains.lead.models import LeadProduct
    ids = {l.id for l in items}
    if not ids:
        return {}
    rows = (await db.execute(select(LeadProduct).where(
        LeadProduct.tenant_id == tenant_id, LeadProduct.lead_id.in_(ids))
        .order_by(LeadProduct.lead_id, LeadProduct.sort_order))).scalars().all()
    grouped: dict = {}
    for p in rows:
        parts = [p.product_name or ""]
        if p.product_spec:
            parts.append(f"({p.product_spec})")
        if p.quantity is not None:
            parts.append(f"x{float(p.quantity):g}")
        if p.remark:
            parts.append(f"[{p.remark}]")
        grouped.setdefault(p.lead_id, []).append("".join(parts))
    return {lid: "; ".join(v) for lid, v in grouped.items()}


@router.get("/export/excel")
async def export_leads_excel(
    keyword: str = Query(None),
    status: str = Query(None),
    owner_id: str = Query(None),
    company_name: str = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    date_field: str = Query(None, description="日期区间筛选字段：created_at(默认) / biz_date"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    from app.config import settings
    items, _ = await service.list_leads(
        db, tenant_id, 1, settings.MAX_EXPORT_ROWS, keyword, status, owner_id,
        company_name=company_name, start_date=start_date, end_date=end_date,
        date_field=date_field, current_user=_user,
    )
    # 导出除列表字段外，补齐详情中「部门/联系人/补充信息」各模块字段
    dept_names = await _lead_department_names(db, tenant_id, items)
    headers = [
        # 列表 & 基本信息
        "项目号", "标题", "公司名称", "部门", "来源", "类别", "客户类型", "行业",
        "业务日期", "报备人", "报备时间", "状态", "评分",
        # 联系人信息
        "联系人", "联系电话", "邮箱",
        # 地区
        "国别", "国家", "省", "市", "区县", "地区",
        # 补充信息
        "需求摘要", "备注",
        "创建时间",
    ]
    category_label = {"self_reported": "自报", "distributed": "分发"}
    country_label = {"domestic": "国内", "overseas": "国外"}
    # 导出与列表/详情同口径：隐藏字段导空、脱敏字段导 "***"。
    # 否则「页面看不到但能导出来」就是一条绕过字段权限的后门。
    from app.domains.lowcode.field_permission import entity_field_restrictions, export_cell
    rst = await entity_field_restrictions(db, tenant_id, "lead", _user.get("roles"))
    c = lambda fid, v: export_cell(rst, fid, v)  # noqa: E731
    rows = []
    for l in items:
        rows.append([
            l.lead_code or "", c("title", l.title or ""), c("company_name", l.company_name or ""),
            c("department_id", dept_names.get(l.department_id, "") if l.department_id else ""),
            c("source", l.source or ""),
            c("category", category_label.get(l.category or "", l.category or "")),
            c("customer_type", l.customer_type or ""),
            c("industry", l.industry or ""),
            c("biz_date", str(l.biz_date) if l.biz_date else ""),
            c("reporter_id", getattr(l, "reporter_name", None) or ""),
            c("reported_at", l.reported_at.strftime("%Y-%m-%d %H:%M") if getattr(l, "reported_at", None) else ""),
            l.status or "", l.score or "",
            c("contact_name", l.contact_name or ""), c("contact_phone", l.contact_phone or ""),
            c("contact_email", l.contact_email or ""),
            c("country_type", country_label.get(l.country_type or "", l.country_type or "")),
            c("country_name", l.country_name or ""),
            l.province or "", l.city or "", l.district or "", c("region", l.region or ""),
            c("demand_summary", l.demand_summary or ""),
            c("remark", l.remark or ""),
            l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "",
        ])
    buf = build_excel("线索列表", headers, rows)
    return excel_response(buf, "leads.xlsx")


@router.get("/import/template")
async def download_lead_import_template(
    _user=Depends(require_permissions("lead:create")),
):
    """下载线索导入模板（对齐申报表单必填/常用字段；含填写说明页）。"""
    buf = build_excel_multi([
        ("线索导入", LEAD_IMPORT_HEADERS, [lead_import_sample_row()]),
        ("填写说明", ["字段", "说明", "示例/可选值"], lead_import_guide_rows()),
    ])
    return excel_response(buf, "lead_import_template.xlsx")


async def _resolve_user_id(db: AsyncSession, tenant_id: str, name):
    """按姓名(real_name 或 username)在租户内匹配用户，返回 user_id；匹配不到返回 None。"""
    if not name or not str(name).strip():
        return None
    from sqlalchemy import select
    from app.domains.auth.models import User as AuthUser
    nm = str(name).strip()
    u = (await db.execute(select(AuthUser).where(
        AuthUser.tenant_id == tenant_id,
        (AuthUser.real_name == nm) | (AuthUser.username == nm)))).scalars().first()
    return u.id if u else None


async def _resolve_department_id(db: AsyncSession, tenant_id: str, name):
    """按部门名称精确匹配（未删）。"""
    if not name or not str(name).strip():
        return None
    from sqlalchemy import select
    from app.domains.organization.models import Department
    nm = str(name).strip()
    d = (await db.execute(select(Department).where(
        Department.tenant_id == tenant_id,
        Department.name == nm,
    ))).scalars().first()
    return d.id if d else None


async def _validate_lead_import_row(
    db: AsyncSession, tenant_id: str, raw: dict,
) -> str | None:
    """预览/导入共用的行级校验，返回错误文案；通过返回 None。"""
    if not raw.get("title"):
        return "项目名称不能为空"
    dept_name = raw.get("department_name")
    if dept_name:
        if not await _resolve_department_id(db, tenant_id, dept_name):
            return f"找不到部门「{dept_name}」，请填写系统中的部门全名"
    reporter_name = raw.get("reporter_name")
    if reporter_name:
        if not await _resolve_user_id(db, tenant_id, reporter_name):
            return f"找不到申报人「{reporter_name}」"
    return None


@router.post("/import/preview")
async def import_leads_preview(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:create")),
):
    """解析 Excel/CSV，返回表头、行数据与行级错误（不落库）。"""
    content = await file.read()
    all_rows = parse_upload_rows(content, file.filename)
    headers, data_rows = rows_for_preview(all_rows)
    if not headers:
        return ok({"headers": [], "rows": [], "duplicates": [], "errors": {}})

    colmap = map_header_row(all_rows[0] if all_rows else ())
    errors: dict[int, str] = {}
    if "title" not in colmap:
        return ok({
            "headers": headers,
            "rows": data_rows,
            "duplicates": [],
            "errors": {0: "未识别表头「项目名称」或「标题」，请下载最新导入模板"},
        })

    preview_i = 0
    for row in all_rows[1:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        raw = row_to_payload(row, colmap)
        err = await _validate_lead_import_row(db, tenant_id, raw)
        if err:
            errors[preview_i] = err
        preview_i += 1

    return ok({"headers": headers, "rows": data_rows, "duplicates": [], "errors": errors})

@router.post("/import/excel")
async def import_leads_excel(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:create")),
):
    """从 Excel/CSV 导入线索并提交情报审批。按表头映射字段，兼容旧版短模板。"""
    from app.domains.lead.schemas import LeadCreate
    content = await file.read()
    all_rows = parse_upload_rows(content, file.filename)
    if not all_rows:
        return ok({"created": 0, "skipped": 0, "errors": ["空文件"]})

    header = all_rows[0]
    colmap = map_header_row(header or ())
    if "title" not in colmap:
        return ok({"created": 0, "skipped": 0, "errors": [
            "未识别表头「项目名称」或「标题」，请下载最新导入模板",
        ]})

    created = 0
    errors: list[str] = []
    create_fields = set(LeadCreate.model_fields)
    for idx, row in enumerate(all_rows[1:], 2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        try:
            raw = row_to_payload(row, colmap)
            title = raw.pop("title", None)
            if not title:
                continue
            dept_name = raw.pop("department_name", None)
            reporter_name = raw.pop("reporter_name", None)
            raw.pop("owner_name", None)  # 负责人列已废弃，兼容旧模板时忽略
            err = await _validate_lead_import_row(db, tenant_id, {
                "title": title,
                "department_name": dept_name,
                "reporter_name": reporter_name,
            })
            if err:
                raise ValueError(err)
            department_id = await _resolve_department_id(db, tenant_id, dept_name)
            reporter_id = await _resolve_user_id(db, tenant_id, reporter_name)

            company = raw.get("company_name") or title
            skip = {
                "company_name", "source", "title",
                "department_id", "reporter_id",
            }
            kwargs = {
                k: v for k, v in raw.items()
                if k in create_fields and k not in skip
            }
            data = LeadCreate(
                title=title,
                company_name=company,
                department_id=department_id,
                reporter_id=reporter_id,
                source=raw.get("source") or "import",
                **kwargs,
            )
            await service.create_lead(db, tenant_id, data, current_user)
            created += 1
        except Exception as e:
            errors.append(f"第{idx}行: {str(e)[:120]}")
    return ok({"created": created, "skipped": 0, "errors": errors})

@router.post("")
async def create_lead(
    body: service.LeadCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:create")),
):
    l = await service.create_lead(db, tenant_id, body, current_user)
    products = await service.list_lead_products(db, tenant_id, l.id)
    return await ok_entity(db, tenant_id, "lead", _lead_dict(l, products, await _lead_department_names(db, tenant_id, [l])), current_user.get("roles"))


@router.get("/{lead_id}")
async def get_lead(
    lead_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    l = await service.get_lead(db, tenant_id, lead_id, _user)
    products = await service.list_lead_products(db, tenant_id, l.id)
    d = _lead_dict(l, products, await _lead_department_names(db, tenant_id, [l]))
    await strip_entity_dicts(db, tenant_id, "lead", [d], _user.get("roles"))  # 字段级权限：读取剔除隐藏扩展字段
    return ok(d)


@router.put("/{lead_id}")
async def update_lead(
    lead_id: str,
    body: service.LeadUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:edit")),
):
    l = await service.update_lead(db, tenant_id, lead_id, body, current_user)
    products = await service.list_lead_products(db, tenant_id, l.id)
    return await ok_entity(db, tenant_id, "lead", _lead_dict(l, products, await _lead_department_names(db, tenant_id, [l])), current_user.get("roles"))


class QualifyBody(BaseModel):
    create_opportunity: bool = False


@router.post("/{lead_id}/qualify")
async def qualify_lead(
    lead_id: str,
    body: Optional[QualifyBody] = None,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:qualify")),
):
    create_opp = body.create_opportunity if body else False
    await service.get_lead(db, tenant_id, lead_id, current_user)  # 数据范围校验
    result = await service.qualify_lead(db, tenant_id, lead_id, current_user, create_opportunity=create_opp)
    return ok(result)


@router.post("/{lead_id}/submit_review")
async def submit_lead_review(
    lead_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:edit")),
):
    """草稿线索提交内勤审核（驳回为终态，不可由此重提）。"""
    l = await service.resubmit_lead_review(db, tenant_id, lead_id, current_user)
    products = await service.list_lead_products(db, tenant_id, l.id)
    return await ok_entity(db, tenant_id, "lead", _lead_dict(l, products), current_user.get("roles"))


class IntelReviewBody(BaseModel):
    decision: str  # include | attack | return | revise | draft
    task_id: str
    customer_newness: Optional[str] = None  # new | old
    return_reason: Optional[str] = None
    opinion: Optional[str] = None
    assess_remark: Optional[str] = None


@router.post("/{lead_id}/intel_review")
async def intel_review_lead(
    lead_id: str,
    body: IntelReviewBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:view")),
):
    """情报审批：收录 / 袭击 / 回退 / 暂存。有对应待办即可裁定。"""
    from app.domains.lead.schemas import LeadIntelReviewIn
    payload = LeadIntelReviewIn(**body.model_dump())
    l = await service.intel_review_lead(
        db, tenant_id, lead_id, current_user,
        decision=payload.decision,
        task_id=payload.task_id,
        customer_newness=payload.customer_newness,
        return_reason=payload.return_reason,
        opinion=payload.opinion,
        assess_remark=payload.assess_remark,
    )
    products = await service.list_lead_products(db, tenant_id, l.id)
    return await ok_entity(
        db, tenant_id, "lead",
        _lead_dict(l, products, await _lead_department_names(db, tenant_id, [l])),
        current_user.get("roles"),
    )


class LeadReactivationBody(BaseModel):
    project_recent: Optional[str] = None
    follow_progress: Optional[str] = None
    site_visit: Optional[str] = None
    report_project_status: str


def _reactivation_record_dict(r) -> dict:
    return {
        "id": r.id,
        "lead_id": r.lead_id,
        "original_lead_code": r.original_lead_code,
        "round_no": r.round_no,
        "project_recent": r.project_recent,
        "follow_progress": r.follow_progress,
        "site_visit": r.site_visit,
        "report_project_status": r.report_project_status,
        "submitted_by_id": r.submitted_by_id,
        "submitted_by_name": r.submitted_by_name,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/{lead_id}/reactivation/records")
async def list_lead_reactivation_records(
    lead_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:view")),
):
    """线索详情：180 天项目激活内容查看（按轮次倒序）。"""
    from app.domains.lead import reactivation as react_svc
    await service.get_lead(db, tenant_id, lead_id, current_user)
    rows = await react_svc.list_reactivation_records(db, tenant_id, lead_id)
    return ok([_reactivation_record_dict(r) for r in rows])


@router.post("/{lead_id}/reactivation/submit")
async def submit_lead_reactivation(
    lead_id: str,
    body: LeadReactivationBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:edit")),
):
    """180 天重激活：申报人/填表人提交项目近况与结果。"""
    from app.domains.lead.schemas import LeadReactivationSubmitIn
    from app.domains.lead import reactivation as react_svc
    payload = LeadReactivationSubmitIn(**body.model_dump())
    l = await react_svc.submit_reactivation(db, tenant_id, lead_id, current_user, payload)
    products = await service.list_lead_products(db, tenant_id, l.id)
    return await ok_entity(
        db, tenant_id, "lead",
        _lead_dict(l, products, await _lead_department_names(db, tenant_id, [l])),
        current_user.get("roles"),
    )


@router.post("/{lead_id}/discard")
async def discard_lead(
    lead_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:discard")),
):
    await service.get_lead(db, tenant_id, lead_id, current_user)  # 数据范围校验
    l = await service.discard_lead(db, tenant_id, lead_id, current_user)
    return await ok_entity(db, tenant_id, "lead", _lead_dict(l), current_user.get("roles"))


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:delete")),
):
    await service.delete_lead(db, tenant_id, lead_id, current_user)
    return ok()


# --- Public Lead Capture Webhook ---

class PublicLeadBody(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    demand_summary: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    source: Optional[str] = "inbound"


public_router = APIRouter(prefix="/api/public/v1", tags=["公开接口"])


@public_router.post("/leads")
async def public_lead_capture(
    body: PublicLeadBody,
    x_tenant_id: str = FastAPIHeader(alias="X-Tenant-Id", default="00000000-0000-0000-0000-000000000001"),
    db: AsyncSession = Depends(get_db),
):
    """Public lead capture webhook. No auth required. Requires X-Tenant-Id header."""
    from app.domains.lead.schemas import LeadCreate
    title = body.company_name or body.contact_name or "网页表单线索"
    data = LeadCreate(
        title=title,
        # company_name is required; fall back to the derived title for anonymous submissions
        company_name=body.company_name or title,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        contact_email=body.contact_email,
        demand_summary=body.demand_summary,
        industry=body.industry,
        region=body.region,
        source=body.source or "inbound",
    )
    system_user = {"sub": "system", "real_name": "系统"}
    # 公开表单线索无归属提交人，直接免审进入线索池（由内勤后续分配/跟进）
    lead = await service.create_lead(db, x_tenant_id, data, system_user, auto_review=False)
    return ok({"id": lead.id, "title": lead.title})


# ---- Batch Operations ----

class BatchStatusBody(BaseModel):
    ids: list[str]
    status: str  # new / following / qualified / discarded


async def _visible_lead_ids(db: AsyncSession, tenant_id: str, user: dict, ids: list[str]) -> list[str]:
    """把批量操作的 id 列表收敛到当前用户数据范围内的那些，口径与列表一致。"""
    from sqlalchemy import select
    from app.common.data_scope import apply_data_scope
    from app.domains.lead.models import Lead
    if not ids:
        return []
    q = select(Lead.id).where(
        Lead.tenant_id == tenant_id, Lead.id.in_(ids), Lead.is_deleted == False)
    q = await apply_data_scope(q, db, tenant_id, user, Lead, "lead")
    return list((await db.execute(q)).scalars().all())


@router.post("/batch_status")
async def batch_status(
    body: BatchStatusBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:edit")),
):
    """Batch update lead status."""
    from sqlalchemy import update
    from app.domains.lead.models import Lead
    if body.status not in ("new", "following", "qualified", "discarded"):
        from app.common.exceptions import BusinessException
        raise BusinessException(message="无效状态")
    # 同 batch_assign：批量改状态也必须落在数据范围内
    ids = await _visible_lead_ids(db, tenant_id, current_user, body.ids)
    if not ids:
        return ok({"updated": 0})
    stmt = update(Lead).where(
        Lead.tenant_id == tenant_id,
        Lead.id.in_(ids),
        Lead.is_deleted == False,
        # 已转化线索锁定，任何人不可再改状态
        Lead.status != "qualified",
    )
    # 批量转化时跳过尚未通过审核的线索，避免绕过审核门禁
    if body.status == "qualified":
        stmt = stmt.where(Lead.review_status == "approved")
    result = await db.execute(stmt.values(status=body.status))
    await db.commit()
    return ok({"updated": result.rowcount})
