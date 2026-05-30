from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.order import service
from app.domains.order.schemas import OrderCreate, OrderUpdate

router = APIRouter(prefix="/api/v1/orders", tags=["订单管理"])

STATUS_LABEL = {
    "draft": "草稿", "confirmed": "已确认", "producing": "生产中",
    "shipped": "已发货", "completed": "已完成", "cancelled": "已取消",
}


def _order_dict(o) -> dict:
    return {
        "id": o.id, "order_no": o.order_no,
        "customer_id": o.customer_id, "project_id": o.project_id, "contract_id": o.contract_id,
        "title": o.title,
        "amount": float(o.amount) if o.amount is not None else None,
        "currency": o.currency, "status": o.status,
        "order_date": str(o.order_date) if o.order_date else None,
        "delivery_date": str(o.delivery_date) if o.delivery_date else None,
        "owner_id": o.owner_id, "owner_name": o.owner_name,
        "remark": o.remark,
        "created_at": o.created_at.isoformat() if o.created_at else "",
        "updated_at": o.updated_at.isoformat() if o.updated_at else "",
    }


@router.get("")
async def list_orders(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    customer_id: str = Query(None),
    status: str = Query(None),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("order:view")),
):
    items, total = await service.list_orders(db, tenant_id, pageNo, pageSize, customer_id, status, keyword)
    return ok({"items": [_order_dict(o) for o in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/export/excel")
async def export_orders_excel(
    customer_id: str = Query(None),
    status: str = Query(None),
    keyword: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("order:view")),
):
    from app.config import settings
    items, _ = await service.list_orders(db, tenant_id, 1, settings.MAX_EXPORT_ROWS, customer_id, status, keyword)
    headers = ["订单号", "标题", "金额", "币种", "状态", "下单日期", "交付日期", "负责人", "创建时间"]
    rows = []
    for o in items:
        rows.append([
            o.order_no, o.title or "",
            float(o.amount) if o.amount is not None else "",
            o.currency or "", STATUS_LABEL.get(o.status or "", o.status or ""),
            str(o.order_date) if o.order_date else "",
            str(o.delivery_date) if o.delivery_date else "",
            o.owner_name or "",
            o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
        ])
    buf = build_excel("订单列表", headers, rows)
    return excel_response(buf, "orders.xlsx")


@router.post("")
async def create_order(
    body: OrderCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("order:create")),
):
    o = await service.create_order(db, tenant_id, body, current_user)
    return ok(_order_dict(o))


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("order:view")),
):
    o = await service.get_order(db, tenant_id, order_id)
    return ok(_order_dict(o))


@router.put("/{order_id}")
async def update_order(
    order_id: str,
    body: OrderUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("order:edit")),
):
    o = await service.update_order(db, tenant_id, order_id, body, current_user)
    return ok(_order_dict(o))


@router.delete("/{order_id}")
async def delete_order(
    order_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("order:delete")),
):
    await service.delete_order(db, tenant_id, order_id, current_user)
    return ok()
