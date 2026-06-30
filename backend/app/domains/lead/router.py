from datetime import date

from fastapi import APIRouter, Depends, Query, Header as FastAPIHeader, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from openpyxl import load_workbook
import io

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.lead import service

router = APIRouter(prefix="/api/v1/leads", tags=["线索管理"])


def _lead_dict(l) -> dict:
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
        "department_id": l.department_id,
        "budget_range": l.budget_range,
        "owner_id": l.owner_id, "owner_name": l.owner_name,
        "status": l.status, "score": l.score,
        "converted_customer_id": l.converted_customer_id,
        "remark": l.remark,
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
    filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
    sort_by: str = Query(None),
    sort_order: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    # 数据范围「本人」= 负责人/创建人/共享给本人；「部门」= 部门子树成员；「全部」= 不限。
    items, total = await service.list_leads(
        db, tenant_id, pageNo, pageSize, keyword, status, owner_id,
        customer_type=customer_type, category=category, country_type=country_type,
        province=province, department_id=department_id, industry=industry,
        company_name=company_name, start_date=start_date, end_date=end_date,
        current_user=_user,
        adv_filter=filter, sort_by=sort_by, sort_order=sort_order,
    )
    return ok({"items": [_lead_dict(l) for l in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/export/excel")
async def export_leads_excel(
    keyword: str = Query(None),
    status: str = Query(None),
    owner_id: str = Query(None),
    company_name: str = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    from app.config import settings
    items, _ = await service.list_leads(
        db, tenant_id, 1, settings.MAX_EXPORT_ROWS, keyword, status, owner_id,
        company_name=company_name, start_date=start_date, end_date=end_date,
        current_user=_user,
    )
    headers = [
        "线索编码", "标题", "公司名称", "联系人", "联系电话", "邮箱",
        "来源", "类别", "客户类型", "行业", "国别", "国家",
        "省", "市", "区县", "地区", "负责人", "状态", "评分", "创建时间",
    ]
    category_label = {"self_reported": "自报", "distributed": "分发"}
    country_label = {"domestic": "国内", "overseas": "国外"}
    rows = []
    for l in items:
        rows.append([
            l.lead_code or "", l.title or "", l.company_name or "",
            l.contact_name or "", l.contact_phone or "", l.contact_email or "",
            l.source or "",
            category_label.get(l.category or "", l.category or ""),
            l.customer_type or "",
            l.industry or "",
            country_label.get(l.country_type or "", l.country_type or ""),
            l.country_name or "",
            l.province or "", l.city or "", l.district or "", l.region or "",
            l.owner_name or "", l.status or "", l.score or "",
            l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "",
        ])
    buf = build_excel("线索列表", headers, rows)
    return excel_response(buf, "leads.xlsx")


@router.post("/import/excel")
async def import_leads_excel(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:create")),
):
    """Import leads from Excel. Columns: 标题, 公司名称, 联系人, 联系电话, 邮箱, 来源, 行业, 地区"""
    from app.domains.lead.schemas import LeadCreate
    content = await file.read()
    wb = load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    created = 0
    errors = []
    for idx, row in enumerate(rows, 2):
        if not row or not row[0]:
            continue
        try:
            data = LeadCreate(
                title=str(row[0]).strip(),
                # company_name is required; fall back to the title when the column is blank
                company_name=str(row[1]).strip() if len(row) > 1 and row[1] else str(row[0]).strip(),
                contact_name=str(row[2]).strip() if len(row) > 2 and row[2] else None,
                contact_phone=str(row[3]).strip() if len(row) > 3 and row[3] else None,
                contact_email=str(row[4]).strip() if len(row) > 4 and row[4] else None,
                source=str(row[5]).strip() if len(row) > 5 and row[5] else "import",
                industry=str(row[6]).strip() if len(row) > 6 and row[6] else None,
                region=str(row[7]).strip() if len(row) > 7 and row[7] else None,
            )
            await service.create_lead(db, tenant_id, data, current_user)
            created += 1
        except Exception as e:
            errors.append(f"第{idx}行: {str(e)[:80]}")
    wb.close()
    return ok({"created": created, "errors": errors})


@router.post("")
async def create_lead(
    body: service.LeadCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:create")),
):
    l = await service.create_lead(db, tenant_id, body, current_user)
    return ok(_lead_dict(l))


@router.get("/{lead_id}")
async def get_lead(
    lead_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("lead:view")),
):
    l = await service.get_lead(db, tenant_id, lead_id)
    return ok(_lead_dict(l))


@router.put("/{lead_id}")
async def update_lead(
    lead_id: str,
    body: service.LeadUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:edit")),
):
    l = await service.update_lead(db, tenant_id, lead_id, body, current_user)
    return ok(_lead_dict(l))


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
    result = await service.qualify_lead(db, tenant_id, lead_id, current_user, create_opportunity=create_opp)
    return ok(result)


@router.post("/{lead_id}/discard")
async def discard_lead(
    lead_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:discard")),
):
    l = await service.discard_lead(db, tenant_id, lead_id, current_user)
    return ok(_lead_dict(l))


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
    lead = await service.create_lead(db, x_tenant_id, data, system_user)
    return ok({"id": lead.id, "title": lead.title})


# ---- Batch Operations ----

class BatchAssignBody(BaseModel):
    ids: list[str]
    owner_id: str
    owner_name: Optional[str] = None


class BatchStatusBody(BaseModel):
    ids: list[str]
    status: str  # new / following / qualified / discarded


@router.post("/batch_assign")
async def batch_assign(
    body: BatchAssignBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("lead:edit")),
):
    """Batch assign leads to a new owner."""
    from sqlalchemy import select, update
    from app.domains.lead.models import Lead
    sample = (await db.execute(
        select(Lead).where(Lead.tenant_id == tenant_id, Lead.id.in_(body.ids), Lead.is_deleted == False).limit(1)
    )).scalar()
    result = await db.execute(
        update(Lead).where(
            Lead.tenant_id == tenant_id,
            Lead.id.in_(body.ids),
            Lead.is_deleted == False,
        ).values(owner_id=body.owner_id, owner_name=body.owner_name)
    )
    await db.commit()
    # 批量改派给他人 → 给新负责人发一条汇总通知
    if body.owner_id and body.owner_id != current_user["sub"] and result.rowcount and sample:
        try:
            from app.common.auto_notify import notify_lead_assigned
            await notify_lead_assigned(
                db, tenant_id, sample.title or sample.company_name or "线索",
                body.owner_id, current_user.get("real_name") or current_user.get("username"),
                sample.id, count=result.rowcount,
            )
        except Exception:
            pass
    return ok({"updated": result.rowcount})


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
    result = await db.execute(
        update(Lead).where(
            Lead.tenant_id == tenant_id,
            Lead.id.in_(body.ids),
            Lead.is_deleted == False,
        ).values(status=body.status)
    )
    await db.commit()
    return ok({"updated": result.rowcount})
