"""Service-level: OpenAPI lead update (idempotent replay with richer body)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.domains.lead.models import Lead
from app.domains.openapi.schemas import OpenLeadCreate
from app.domains.openapi.service import create_lead_from_openapi, update_lead_from_openapi


TENANT = "00000000-0000-0000-0000-000000000001"


class _Ctx:
    def __init__(self):
        self.tenant_id = TENANT
        self.app_id = "test-openapi-app"
        self.app_key = "ak_test"


@pytest.fixture
async def db():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_update_lead_from_openapi_fills_reported_at(db):
    """Same lead id + richer body should update fields (not 409 / not duplicate)."""
    ctx = _Ctx()
    title = f"LOCAL-LEAD-UT-{uuid.uuid4().hex[:8]}"
    lead_id = None
    try:
        first = await create_lead_from_openapi(
            db, ctx,
            OpenLeadCreate(title=title, company_name="UT Co", source="test"),
        )
        lead_id = first["id"]
        # create_lead defaults reported_at to now when omitted
        assert first.get("reported_at")

        reported = datetime(2026, 6, 16, 2, 28, 25, tzinfo=timezone.utc)
        second = await update_lead_from_openapi(
            db, ctx, lead_id,
            OpenLeadCreate(
                title=title,
                company_name="UT Co",
                source="test",
                reported_at=reported,
            ),
        )
        assert second["id"] == lead_id
        assert second.get("reported_at") == "2026-06-16T02:28:25+00:00"

        rows = (await db.execute(
            select(Lead).where(Lead.tenant_id == TENANT, Lead.title == title, Lead.is_deleted == False)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].reported_at == reported
    finally:
        if lead_id:
            await db.execute(delete(Lead).where(Lead.id == lead_id, Lead.tenant_id == TENANT))
            await db.commit()
