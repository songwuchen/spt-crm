from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.tender import service
from app.domains.tender.schemas import TenderCreate, TenderUpdate

router = APIRouter(prefix="/api/v1/tenders", tags=["标书管理"])

STATUS_LABEL = {
    "preparing": "编制中", "submitted": "已投标", "won": "中标",
    "lost": "未中标", "cancelled": "已取消",
}


def _tender_dict(t) -> dict:
    return {
        "id": t.id, "tender_no": t.tender_no,
        "customer_id": t.customer_id, "project_id": t.project_id,
        "title": t.title,
        "bid_amount": float(t.bid_amount) if t.bid_amount is not None else None,
        "budget_amount": float(t.budget_amount) if t.budget_amount is not None else None,
        "status": t.status,
        "submit_date": str(t.submit_date) if t.submit_date else None,
        "open_date": str(t.open_date) if t.open_date else None,
        "result": t.result,
        "owner_id": t.owner_id, "owner_name": t.owner_name,
        "remark": t.remark,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }


@router.get("")
async def list_tenders(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    customer_id: str = Query(None),
    status: str = Query(None),
    keyword: str = Query(None),
    filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
    sort_by: str = Query(None),
    sort_order: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("tender:view")),
):
    items, total = await service.list_tenders(
        db, tenant_id, pageNo, pageSize, customer_id, status, keyword,
        adv_filter=filter, sort_by=sort_by, sort_order=sort_order, current_user=_user)
    return ok({"items": [_tender_dict(t) for t in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/export/excel")
async def export_tenders_excel(
    customer_id: str = Query(None),
    status: str = Query(None),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("tender:view")),
):
    from app.config import settings
    # 导出与列表同口径过滤数据范围，否则「列表看不到但能导出来」就是绕过范围的后门
    items, _ = await service.list_tenders(
        db, tenant_id, 1, settings.MAX_EXPORT_ROWS, customer_id, status, keyword, current_user=_user)
    headers = ["标书号", "标题", "投标金额", "预算金额", "状态", "提交日期", "开标日期", "结果", "负责人", "创建时间"]
    rows = []
    for t in items:
        rows.append([
            t.tender_no, t.title or "",
            float(t.bid_amount) if t.bid_amount is not None else "",
            float(t.budget_amount) if t.budget_amount is not None else "",
            STATUS_LABEL.get(t.status or "", t.status or ""),
            str(t.submit_date) if t.submit_date else "",
            str(t.open_date) if t.open_date else "",
            t.result or "", t.owner_name or "",
            t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
        ])
    buf = build_excel("标书列表", headers, rows)
    return excel_response(buf, "tenders.xlsx")


@router.post("")
async def create_tender(
    body: TenderCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("tender:create")),
):
    t = await service.create_tender(db, tenant_id, body, current_user)
    return ok(_tender_dict(t))


@router.get("/{tender_id}")
async def get_tender(
    tender_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("tender:view")),
):
    t = await service.get_tender(db, tenant_id, tender_id, _user)
    return ok(_tender_dict(t))


@router.put("/{tender_id}")
async def update_tender(
    tender_id: str,
    body: TenderUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("tender:edit")),
):
    t = await service.update_tender(db, tenant_id, tender_id, body, current_user)
    return ok(_tender_dict(t))


@router.delete("/{tender_id}")
async def delete_tender(
    tender_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("tender:delete")),
):
    await service.delete_tender(db, tenant_id, tender_id, current_user)
    return ok()
