from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions
from app.common.schemas import ok
from app.domains.product import service
from app.domains.product.schemas import (
    ProductCreate, ProductUpdate,
    ProductCategoryCreate, ProductCategoryUpdate,
)

router = APIRouter(prefix="/api/v1/products", tags=["产品目录"])


def _product_dict(p) -> dict:
    return {
        "id": p.id, "product_code": p.product_code, "name": p.name,
        "category_id": p.category_id, "item_type": p.item_type,
        "spec": p.spec, "unit": p.unit,
        "unit_price": float(p.unit_price) if p.unit_price is not None else None,
        "cost_price": float(p.cost_price) if p.cost_price is not None else None,
        "leadtime_days": p.leadtime_days,
        "is_active": p.is_active, "remark": p.remark,
        "extra_json": p.extra_json,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }


def _category_dict(c) -> dict:
    return {
        "id": c.id, "name": c.name, "parent_id": c.parent_id,
        "sort_order": c.sort_order, "description": c.description,
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }


# ---- Category ----

@router.get("/categories")
async def list_categories(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("product:view")),
):
    items = await service.list_categories(db, tenant_id)
    return ok([_category_dict(c) for c in items])


@router.post("/categories")
async def create_category(
    body: ProductCategoryCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("product:edit")),
):
    c = await service.create_category(db, tenant_id, body)
    return ok(_category_dict(c))


@router.put("/categories/{category_id}")
async def update_category(
    category_id: str,
    body: ProductCategoryUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("product:edit")),
):
    c = await service.update_category(db, tenant_id, category_id, body)
    return ok(_category_dict(c))


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("product:edit")),
):
    await service.delete_category(db, tenant_id, category_id)
    return ok()


# ---- Product ----

@router.get("")
async def list_products(
    pageNo: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    category_id: str = Query(None),
    item_type: str = Query(None),
    is_active: bool = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("product:view")),
):
    items, total = await service.list_products(db, tenant_id, pageNo, pageSize, keyword, category_id, item_type, is_active)
    return ok({"items": [_product_dict(p) for p in items], "total": total, "pageNo": pageNo, "pageSize": pageSize})


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("product:view")),
):
    p = await service.get_product(db, tenant_id, product_id)
    return ok(_product_dict(p))


@router.post("")
async def create_product(
    body: ProductCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("product:create")),
):
    p = await service.create_product(db, tenant_id, body, current_user)
    return ok(_product_dict(p))


@router.put("/{product_id}")
async def update_product(
    product_id: str,
    body: ProductUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("product:edit")),
):
    p = await service.update_product(db, tenant_id, product_id, body, current_user)
    return ok(_product_dict(p))


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("product:delete")),
):
    await service.delete_product(db, tenant_id, product_id, current_user)
    return ok()
