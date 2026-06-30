from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.guarantee import service
from app.domains.guarantee.schemas import GuaranteeCreate, GuaranteeUpdate, GuaranteeReturn

router = APIRouter(prefix="/api/v1/guarantees", tags=["保函管理"])

TYPE_LABEL = {
    "performance": "履约保函", "advance": "预付保函", "quality": "质量保函",
    "bid": "投标保证金", "deposit": "履约保证金",
}
STATUS_LABEL = {"active": "生效中", "returned": "已退还", "expired": "已逾期", "cancelled": "已取消"}


def _g_dict(g) -> dict:
    return {
        "id": g.id, "guarantee_no": g.guarantee_no, "type": g.type, "direction": g.direction,
        "contract_id": g.contract_id, "project_id": g.project_id,
        "customer_id": g.customer_id, "customer_name": g.customer_name,
        "amount": float(g.amount) if g.amount is not None else None,
        "issuer": g.issuer,
        "fee": float(g.fee) if g.fee is not None else None,
        "rate": float(g.rate) if g.rate is not None else None,
        "effective_date": str(g.effective_date) if g.effective_date else None,
        "expiry_date": str(g.expiry_date) if g.expiry_date else None,
        "return_date": str(g.return_date) if g.return_date else None,
        "status": g.status, "owner_id": g.owner_id, "owner_name": g.owner_name,
        "remark": g.remark, "created_by_name": g.created_by_name,
        "created_at": g.created_at.isoformat() if g.created_at else "",
    }


@router.get("/summary")
async def summary(tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                  _u=Depends(require_permissions("guarantee:view"))):
    return ok(await service.summary(db, tenant_id))


@router.get("/expiring")
async def expiring(days: int = Query(30, ge=1, le=365), tenant_id: str = Depends(get_tenant_id),
                   db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("guarantee:view"))):
    return ok([_g_dict(g) for g in await service.list_expiring(db, tenant_id, days)])


@router.post("/notify")
async def notify(days: int = Query(30, ge=1, le=365), tenant_id: str = Depends(get_tenant_id),
                 db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("guarantee:view"))):
    n = await service.check_expiring_and_notify(db, tenant_id, days)
    return ok({"notified": n})


@router.get("/export/excel")
async def export_excel(type: str = Query(None), status: str = Query(None), keyword: str = Query(None),
                       tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                       _u=Depends(require_permissions("guarantee:view"))):
    from app.config import settings
    items, _ = await service.list_guarantees(db, tenant_id, 1, settings.MAX_EXPORT_ROWS, type, status, keyword)
    headers = ["保函编号", "类型", "方向", "客户", "金额", "出具机构", "生效日", "到期日", "状态", "负责人"]
    rows = []
    for g in items:
        rows.append([
            g.guarantee_no, TYPE_LABEL.get(g.type or "", g.type or ""),
            "我方开出" if g.direction == "outgoing" else "我方收取",
            g.customer_name or "", float(g.amount or 0), g.issuer or "",
            str(g.effective_date) if g.effective_date else "",
            str(g.expiry_date) if g.expiry_date else "",
            STATUS_LABEL.get(g.status or "", g.status or ""), g.owner_name or "",
        ])
    buf = build_excel("保函台账", headers, rows)
    return excel_response(buf, "guarantees.xlsx")


@router.get("")
async def list_guarantees(pageNo: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                          type: str = Query(None), status: str = Query(None), keyword: str = Query(None),
                          filter: str = Query(None, description="高级筛选 FilterDsl(JSON)"),
                          sort_by: str = Query(None), sort_order: str = Query(None),
                          tenant_id: str = Depends(get_tenant_id), db: AsyncSession = Depends(get_db),
                          u=Depends(require_permissions("guarantee:view"))):
    items, total = await service.list_guarantees(db, tenant_id, pageNo, pageSize, type, status, keyword,
                                                 adv_filter=filter, sort_by=sort_by, sort_order=sort_order,
                                                 current_user=u)
    return ok({"items": [_g_dict(g) for g in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.post("")
async def create_guarantee(body: GuaranteeCreate, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), u=Depends(require_permissions("guarantee:edit"))):
    return ok(_g_dict(await service.create_guarantee(db, tenant_id, body, u)))


@router.get("/{gid}")
async def get_guarantee(gid: str, tenant_id: str = Depends(get_tenant_id),
                        db: AsyncSession = Depends(get_db), _u=Depends(require_permissions("guarantee:view"))):
    return ok(_g_dict(await service.get_guarantee(db, tenant_id, gid)))


@router.put("/{gid}")
async def update_guarantee(gid: str, body: GuaranteeUpdate, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), u=Depends(require_permissions("guarantee:edit"))):
    return ok(_g_dict(await service.update_guarantee(db, tenant_id, gid, body, u)))


@router.post("/{gid}/return")
async def return_guarantee(gid: str, body: GuaranteeReturn, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), u=Depends(require_permissions("guarantee:edit"))):
    return ok(_g_dict(await service.mark_returned(db, tenant_id, gid, body, u)))


@router.delete("/{gid}")
async def delete_guarantee(gid: str, tenant_id: str = Depends(get_tenant_id),
                           db: AsyncSession = Depends(get_db), u=Depends(require_permissions("guarantee:edit"))):
    await service.delete_guarantee(db, tenant_id, gid, u)
    return ok()
