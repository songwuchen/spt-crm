from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.domains.product.models import Product, ProductCategory
from app.domains.product.schemas import (
    ProductCreate, ProductUpdate,
    ProductCategoryCreate, ProductCategoryUpdate,
)


# ---- Category ----

async def list_categories(db: AsyncSession, tenant_id: str):
    result = await db.execute(
        select(ProductCategory)
        .where(ProductCategory.tenant_id == tenant_id)
        .order_by(ProductCategory.sort_order, ProductCategory.name)
    )
    return result.scalars().all()


async def create_category(db: AsyncSession, tenant_id: str, data: ProductCategoryCreate):
    cat = ProductCategory(tenant_id=tenant_id, **data.model_dump())
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def update_category(db: AsyncSession, tenant_id: str, category_id: str, data: ProductCategoryUpdate):
    cat = (await db.execute(
        select(ProductCategory).where(ProductCategory.tenant_id == tenant_id, ProductCategory.id == category_id)
    )).scalar()
    if not cat:
        raise BusinessException(message="分类不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, tenant_id: str, category_id: str):
    cat = (await db.execute(
        select(ProductCategory).where(ProductCategory.tenant_id == tenant_id, ProductCategory.id == category_id)
    )).scalar()
    if not cat:
        raise BusinessException(message="分类不存在")
    # Check if any products reference this category
    count = (await db.execute(
        select(func.count(Product.id)).where(Product.tenant_id == tenant_id, Product.category_id == category_id)
    )).scalar() or 0
    if count > 0:
        raise BusinessException(f"该分类下有 {count} 个产品，无法删除")
    await db.delete(cat)
    await db.commit()


# ---- Product ----

async def list_products(
    db: AsyncSession, tenant_id: str,
    page: int, page_size: int,
    keyword: str | None = None,
    category_id: str | None = None,
    item_type: str | None = None,
    is_active: bool | None = None,
    current_user: dict | None = None,
    adv_filter: str | None = None, sort_by: str | None = None, sort_order: str | None = None,
):
    base = select(Product).where(Product.tenant_id == tenant_id)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(or_(
            Product.name.ilike(kw),
            Product.product_code.ilike(kw),
            Product.spec.ilike(kw),
        ))
    if category_id:
        base = base.where(Product.category_id == category_id)
    if item_type:
        base = base.where(Product.item_type == item_type)
    if is_active is not None:
        base = base.where(Product.is_active == is_active)

    # 高级筛选（多字段/多条件）。产品无 owner，ctx.user_id 传 None。
    from app.common.search import filter_clause_or_400, resolve_sort
    clause = filter_clause_or_400("product", adv_filter, {"user_id": None})
    if clause is not None:
        base = base.where(clause)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    order = resolve_sort("product", sort_by, sort_order, Product.product_code.asc())
    items = (await db.execute(
        base.order_by(order).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_product(db: AsyncSession, tenant_id: str, product_id: str):
    p = (await db.execute(
        select(Product).where(Product.tenant_id == tenant_id, Product.id == product_id)
    )).scalar()
    if not p:
        raise BusinessException(message="产品不存在")
    return p


async def create_product(db: AsyncSession, tenant_id: str, data: ProductCreate, current_user: dict):
    # Check unique code
    exists = (await db.execute(
        select(Product.id).where(Product.tenant_id == tenant_id, Product.product_code == data.product_code)
    )).scalar()
    if exists:
        raise BusinessException(f"产品编码 {data.product_code} 已存在")
    p = Product(tenant_id=tenant_id, **data.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_product(db: AsyncSession, tenant_id: str, product_id: str, data: ProductUpdate, current_user: dict):
    p = await get_product(db, tenant_id, product_id)
    update_data = data.model_dump(exclude_unset=True)
    # Check unique code if changing
    if "product_code" in update_data and update_data["product_code"] != p.product_code:
        exists = (await db.execute(
            select(Product.id).where(
                Product.tenant_id == tenant_id,
                Product.product_code == update_data["product_code"],
                Product.id != product_id,
            )
        )).scalar()
        if exists:
            raise BusinessException(f"产品编码 {update_data['product_code']} 已存在")
    for k, v in update_data.items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p


async def delete_product(db: AsyncSession, tenant_id: str, product_id: str, current_user: dict):
    p = await get_product(db, tenant_id, product_id)
    await db.delete(p)
    await db.commit()
