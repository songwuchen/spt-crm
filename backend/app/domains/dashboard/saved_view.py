"""Saved filter views — users can save named view presets for list pages.

一个「视图」可保存：高级筛选条件(filters) + 列配置(columns) + 排序(sort_by/sort_order)。
可见性 visibility：private(仅自己) / tenant(本租户共享，仅创建者可改删)。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from typing import Optional
import json

from app.database import TenantScopedBase
from app.dependencies import get_db, get_current_user
from app.common.schemas import ok


class SavedView(TenantScopedBase):
    __tablename__ = "saved_views"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "customers", "leads"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: 快捷筛选 + 高级筛选 DSL
    columns_json: Mapped[str | None] = mapped_column(Text)           # JSON: {hidden:[], order:[]}
    sort_by: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[str | None] = mapped_column(String(8))        # asc / desc
    visibility: Mapped[str] = mapped_column(String(16), default="private")  # private / tenant
    is_default: Mapped[bool] = mapped_column(default=False)


class SavedViewCreate(BaseModel):
    page: str
    name: str
    filters: dict
    columns: Optional[dict] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    visibility: str = "private"
    is_default: bool = False


class SavedViewUpdate(BaseModel):
    name: Optional[str] = None
    filters: Optional[dict] = None
    columns: Optional[dict] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    visibility: Optional[str] = None
    is_default: Optional[bool] = None


router = APIRouter(prefix="/api/v1/saved-views", tags=["保存视图"])


def _view_dict(v: SavedView, current_user_id: str) -> dict:
    return {
        "id": v.id, "name": v.name, "page": v.page,
        "filters": json.loads(v.filters_json) if v.filters_json else {},
        "columns": json.loads(v.columns_json) if v.columns_json else None,
        "sort_by": v.sort_by, "sort_order": v.sort_order,
        "visibility": v.visibility or "private",
        "is_default": v.is_default,
        "user_id": v.user_id,
        "is_owner": v.user_id == current_user_id,
    }


@router.get("")
async def list_views(page: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user["sub"]
    tenant_id = current_user["tenant_id"]
    # 自己的视图 + 本租户共享视图
    items = (await db.execute(
        select(SavedView).where(
            SavedView.tenant_id == tenant_id,
            SavedView.page == page,
            (SavedView.user_id == user_id) | (SavedView.visibility == "tenant"),
        ).order_by(SavedView.is_default.desc(), SavedView.created_at.desc())
    )).scalars().all()
    return ok([_view_dict(v, user_id) for v in items])


@router.post("")
async def create_view(body: SavedViewCreate, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user["sub"]
    tenant_id = current_user["tenant_id"]

    # If setting as default, unset this user's other defaults for the same page
    if body.is_default:
        existing = (await db.execute(
            select(SavedView).where(
                SavedView.tenant_id == tenant_id,
                SavedView.user_id == user_id, SavedView.page == body.page,
                SavedView.is_default == True,
            )
        )).scalars().all()
        for v in existing:
            v.is_default = False

    view = SavedView(
        tenant_id=tenant_id, user_id=user_id, page=body.page,
        name=body.name, filters_json=json.dumps(body.filters),
        columns_json=json.dumps(body.columns) if body.columns is not None else None,
        sort_by=body.sort_by, sort_order=body.sort_order,
        visibility=body.visibility if body.visibility in ("private", "tenant") else "private",
        is_default=body.is_default,
    )
    db.add(view)
    await db.commit()
    return ok({"id": view.id, "name": view.name})


@router.put("/{view_id}")
async def update_view(view_id: str, body: SavedViewUpdate, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.common.exceptions import BusinessException
    user_id = current_user["sub"]
    tenant_id = current_user["tenant_id"]
    view = (await db.execute(
        select(SavedView).where(SavedView.id == view_id, SavedView.tenant_id == tenant_id, SavedView.user_id == user_id)
    )).scalar_one_or_none()
    if not view:
        raise BusinessException(code=404, message="视图不存在或无权修改")
    if body.is_default:
        existing = (await db.execute(
            select(SavedView).where(
                SavedView.tenant_id == tenant_id, SavedView.user_id == user_id,
                SavedView.page == view.page, SavedView.is_default == True, SavedView.id != view_id,
            )
        )).scalars().all()
        for v in existing:
            v.is_default = False
    if body.name is not None:
        view.name = body.name
    if body.filters is not None:
        view.filters_json = json.dumps(body.filters)
    if body.columns is not None:
        view.columns_json = json.dumps(body.columns)
    if body.sort_by is not None:
        view.sort_by = body.sort_by
    if body.sort_order is not None:
        view.sort_order = body.sort_order
    if body.visibility is not None and body.visibility in ("private", "tenant"):
        view.visibility = body.visibility
    if body.is_default is not None:
        view.is_default = body.is_default
    await db.commit()
    return ok(None)


@router.delete("/{view_id}")
async def delete_view(view_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.common.exceptions import BusinessException
    view = (await db.execute(
        select(SavedView).where(SavedView.id == view_id, SavedView.tenant_id == current_user["tenant_id"], SavedView.user_id == current_user["sub"])
    )).scalar_one_or_none()
    if not view:
        raise BusinessException(code=404, message="视图不存在或无权删除")
    await db.delete(view)
    await db.commit()
    return ok(None)
