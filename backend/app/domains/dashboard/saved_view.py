"""Saved filter views — users can save named filter presets for list pages."""
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
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of filter params
    is_default: Mapped[bool] = mapped_column(default=False)


class SavedViewCreate(BaseModel):
    page: str
    name: str
    filters: dict
    is_default: bool = False


class SavedViewUpdate(BaseModel):
    name: Optional[str] = None
    filters: Optional[dict] = None
    is_default: Optional[bool] = None


router = APIRouter(prefix="/api/v1/saved-views", tags=["保存视图"])


@router.get("")
async def list_views(page: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user["sub"]
    items = (await db.execute(
        select(SavedView).where(
            SavedView.user_id == user_id,
            SavedView.page == page,
            SavedView.is_deleted == False,
        ).order_by(SavedView.is_default.desc(), SavedView.created_at.desc())
    )).scalars().all()
    return ok([{
        "id": v.id, "name": v.name, "page": v.page,
        "filters": json.loads(v.filters_json), "is_default": v.is_default,
    } for v in items])


@router.post("")
async def create_view(body: SavedViewCreate, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.dependencies import get_tenant_id
    user_id = current_user["sub"]
    tenant_id = current_user["tenant_id"]

    # If setting as default, unset others
    if body.is_default:
        existing = (await db.execute(
            select(SavedView).where(
                SavedView.user_id == user_id, SavedView.page == body.page,
                SavedView.is_default == True, SavedView.is_deleted == False,
            )
        )).scalars().all()
        for v in existing:
            v.is_default = False

    view = SavedView(
        tenant_id=tenant_id, user_id=user_id, page=body.page,
        name=body.name, filters_json=json.dumps(body.filters), is_default=body.is_default,
    )
    db.add(view)
    await db.commit()
    return ok({"id": view.id, "name": view.name})


@router.put("/{view_id}")
async def update_view(view_id: str, body: SavedViewUpdate, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.common.exceptions import BusinessException
    view = (await db.execute(
        select(SavedView).where(SavedView.id == view_id, SavedView.user_id == current_user["sub"])
    )).scalar_one_or_none()
    if not view:
        raise BusinessException(code=404, message="视图不存在")
    if body.name is not None:
        view.name = body.name
    if body.filters is not None:
        view.filters_json = json.dumps(body.filters)
    if body.is_default is not None:
        view.is_default = body.is_default
    await db.commit()
    return ok(None)


@router.delete("/{view_id}")
async def delete_view(view_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.common.exceptions import BusinessException
    view = (await db.execute(
        select(SavedView).where(SavedView.id == view_id, SavedView.user_id == current_user["sub"])
    )).scalar_one_or_none()
    if not view:
        raise BusinessException(code=404, message="视图不存在")
    view.is_deleted = True
    await db.commit()
    return ok(None)
