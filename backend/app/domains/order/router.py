from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.common.export import build_excel, excel_response
from app.domains.order import service
from app.domains.order.schemas import OrderCreate, OrderUpdate, OrderShip

router = APIRouter(prefix="/api/v1/orders", tags=["订单管理"])

STATUS_LABEL = {
    "draft": "草稿", "confirmed": "已确认", "producing": "生产中",
    "shipped": "已发货", "completed": "已完成", "cancelled": "已取消",
}


def _line_dict(ln) -> dict:
    return {
        "id": ln.id, "product_id": ln.product_id, "product_name": ln.product_name,
        "spec": ln.spec, "unit": ln.unit,
        "quantity": float(ln.quantity) if ln.quantity is not None else 0,
        "unit_price": float(ln.unit_price) if ln.unit_price is not None else 0,
        "amount": float(ln.amount) if ln.amount is not None else 0,
        "shipped_quantity": float(ln.shipped_quantity) if ln.shipped_quantity is not None else 0,
        "sort_order": ln.sort_order,
    }


def _order_dict(o, lines=None) -> dict:
    d = {
        "id": o.id, "order_no": o.order_no,
        "customer_id": o.customer_id, "project_id": o.project_id, "contract_id": o.contract_id,
        "title": o.title,
        "amount": float(o.amount) if o.amount is not None else None,
        "currency": o.currency, "status": o.status,
        "order_date": str(o.order_date) if o.order_date else None,
        "delivery_date": str(o.delivery_date) if o.delivery_date else None,
        "owner_id": o.owner_id, "owner_name": o.owner_name,
        "remark": o.remark, "custom_fields_json": o.custom_fields_json,
        "created_at": o.created_at.isoformat() if o.created_at else "",
        "updated_at": o.updated_at.isoformat() if o.updated_at else "",
    }
    if lines is not None:
        d["lines"] = [_line_dict(ln) for ln in lines]
        d["ship_status"] = service.ship_status(lines)
    return d


@router.get("")
async def list_orders(
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
    _user=Depends(require_permissions("order:view")),
):
    items, total = await service.list_orders(
        db, tenant_id, pageNo, pageSize, customer_id, status, keyword,
        adv_filter=filter, sort_by=sort_by, sort_order=sort_order, current_user=_user)
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
    lines = await service.list_lines(db, tenant_id, o.id)
    return ok(_order_dict(o, lines))


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("order:view")),
):
    o = await service.get_order(db, tenant_id, order_id)
    lines = await service.list_lines(db, tenant_id, order_id)
    return ok(_order_dict(o, lines))


@router.put("/{order_id}")
async def update_order(
    order_id: str,
    body: OrderUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("order:edit")),
):
    o = await service.update_order(db, tenant_id, order_id, body, current_user)
    lines = await service.list_lines(db, tenant_id, order_id)
    return ok(_order_dict(o, lines))


@router.post("/{order_id}/submit")
async def submit_order(
    order_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("order:edit")),
):
    """提交订单审批（内勤发起）。按 order 审批策略自动建立审批流。"""
    o = await service.submit_for_approval(db, tenant_id, order_id, current_user)
    lines = await service.list_lines(db, tenant_id, order_id)
    return ok(_order_dict(o, lines))


@router.post("/{order_id}/ship")
async def ship_order(
    order_id: str,
    body: OrderShip,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("order:edit")),
):
    """发货：部分发货（按行登记数量）或一键全部发货。"""
    o = await service.ship_order(db, tenant_id, order_id, body, current_user)
    lines = await service.list_lines(db, tenant_id, order_id)
    return ok(_order_dict(o, lines))


@router.delete("/{order_id}")
async def delete_order(
    order_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("order:delete")),
):
    await service.delete_order(db, tenant_id, order_id, current_user)
    return ok()
