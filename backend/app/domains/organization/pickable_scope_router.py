# -*- coding: utf-8 -*-
"""可选范围管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions, get_current_user
from app.common.schemas import ok
from app.domains.organization import pickable_scope_service as svc

router = APIRouter(prefix="/api/admin/v1/tenant/pickable-scopes", tags=["可选范围"])


class ScopeCreate(BaseModel):
    code: str
    name: str
    kind: str = "person"
    description: str | None = None
    rules: dict = Field(default_factory=dict)


class ScopeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rules: dict | None = None


@router.get("")
async def list_pickable_scopes(
    kind: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:view")),
):
    rows = await svc.list_scopes(db, tenant_id, kind=kind)
    await db.commit()  # persist preset ensure
    return ok([svc.scope_to_dict(s) for s in rows])


@router.post("")
async def create_pickable_scope(
    body: ScopeCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    s = await svc.create_scope(
        db, tenant_id,
        code=body.code, name=body.name, kind=body.kind,
        description=body.description, rules=body.rules,
    )
    return ok(svc.scope_to_dict(s))


@router.get("/{scope_id}")
async def get_pickable_scope(
    scope_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:view")),
):
    s = await svc.get_scope_by_id(db, tenant_id, scope_id)
    return ok(svc.scope_to_dict(s))


@router.put("/{scope_id}")
async def update_pickable_scope(
    scope_id: str,
    body: ScopeUpdate,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    s = await svc.update_scope(
        db, tenant_id, scope_id,
        name=body.name, description=body.description, rules=body.rules,
    )
    return ok(svc.scope_to_dict(s))


@router.delete("/{scope_id}")
async def delete_pickable_scope(
    scope_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    await svc.delete_scope(db, tenant_id, scope_id)
    return ok()


# 设计器下拉：任意登录用户可读（仅 code/name/kind）
lc_router = APIRouter(prefix="/api/v1/lc", tags=["扩展平台-可选范围"])


@lc_router.get("/pickable-scopes")
async def lc_list_pickable_scopes(
    kind: str | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    rows = await svc.list_scopes(db, tenant_id, kind=kind)
    await db.commit()
    return ok([
        {"id": s.id, "code": s.code, "name": s.name, "kind": s.kind, "description": s.description}
        for s in rows
    ])
