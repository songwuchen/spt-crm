"""Idempotency-Key handling for Open API write endpoints.

Contract:
- A write request MUST carry an ``Idempotency-Key`` header.
- First time seen → run the producer, store its response, return it.
- Replay with the SAME key + SAME request body → return the stored response
  (with ``"idempotent_replay": true``), the producer does NOT run again.
- Replay with the SAME key but a DIFFERENT body → conflict.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid, utcnow
from app.domains.openapi.models import OpenApiIdempotencyKey
from app.domains.openapi.auth import OpenApiContext
from app.domains.openapi.errors import (
    OpenApiException, CRM_VALIDATION_ERROR, CRM_IDEMPOTENCY_CONFLICT,
)

TTL_HOURS = 24


async def _lookup(db: AsyncSession, tenant_id: str, app_key: str, key: str):
    return (await db.execute(
        select(OpenApiIdempotencyKey).where(
            OpenApiIdempotencyKey.tenant_id == tenant_id,
            OpenApiIdempotencyKey.app_key == app_key,
            OpenApiIdempotencyKey.idempotency_key == key,
        )
    )).scalar_one_or_none()


async def run_idempotent(db: AsyncSession, ctx: OpenApiContext, request: Request, producer):
    """Execute ``producer`` (an async fn returning a JSON-able dict) at most once
    per Idempotency-Key. Returns the response data dict."""
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise OpenApiException(
            CRM_VALIDATION_ERROR, "写操作必须提供 Idempotency-Key 请求头", http_status=400,
        )

    raw = await request.body()
    req_hash = hashlib.sha256(
        (request.method + "\n" + request.url.path + "\n").encode() + (raw or b"")
    ).hexdigest()

    existing = await _lookup(db, ctx.tenant_id, ctx.app_key, key)
    if existing:
        if existing.request_hash != req_hash:
            raise OpenApiException(
                CRM_IDEMPOTENCY_CONFLICT, "Idempotency-Key 已用于不同的请求", http_status=409,
            )
        if existing.status == "completed":
            return {**(existing.response_json or {}), "idempotent_replay": True}
        raise OpenApiException(
            CRM_IDEMPOTENCY_CONFLICT, "相同请求正在处理中，请稍后重试", http_status=409,
        )

    # Claim the key first so concurrent duplicates collide on the unique index.
    rec = OpenApiIdempotencyKey(
        id=generate_uuid(), tenant_id=ctx.tenant_id, app_key=ctx.app_key,
        idempotency_key=key, request_hash=req_hash, status="processing",
        expires_at=(utcnow() + timedelta(hours=TTL_HOURS)).isoformat(),
    )
    db.add(rec)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Lost the race — another request claimed the same key concurrently.
        other = await _lookup(db, ctx.tenant_id, ctx.app_key, key)
        if other and other.status == "completed" and other.request_hash == req_hash:
            return {**(other.response_json or {}), "idempotent_replay": True}
        raise OpenApiException(
            CRM_IDEMPOTENCY_CONFLICT, "相同请求正在处理中，请稍后重试", http_status=409,
        )

    data = await producer()

    rec.response_json = data
    rec.status = "completed"
    rec.status_code = 200
    await db.commit()
    return data
