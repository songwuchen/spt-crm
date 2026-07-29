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


async def test_create_lead_from_openapi_normalizes_customer_type(db):
    """Chinese JDY label → dict_code; response exposes customer_type."""
    from app.domains.admin.models import DataDictionary
    from app.domains.openapi.service import resolve_customer_type

    ctx = _Ctx()
    # Ensure dict rows exist for this tenant (idempotent soft upsert for UT).
    for code, label, order in (
        ("terminal_soe", "终端客户-央企/国企", 1),
        ("design_institute", "设计院", 4),
    ):
        existing = (
            await db.execute(
                select(DataDictionary).where(
                    DataDictionary.tenant_id == TENANT,
                    DataDictionary.dict_type == "customer_type",
                    DataDictionary.dict_code == code,
                    DataDictionary.is_deleted == False,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(DataDictionary(
                id=str(uuid.uuid4()),
                tenant_id=TENANT,
                dict_type="customer_type",
                dict_code=code,
                dict_label=label,
                sort_order=order,
                enabled=True,
            ))
    await db.commit()

    assert await resolve_customer_type(db, TENANT, "terminal_soe") == "terminal_soe"
    assert await resolve_customer_type(db, TENANT, "终端客户-央企/国企") == "terminal_soe"
    assert await resolve_customer_type(db, TENANT, "总包") == "general_contractor"
    assert await resolve_customer_type(db, TENANT, "未知类型XYZ") == "未知类型XYZ"

    title = f"LOCAL-LEAD-CT-{uuid.uuid4().hex[:8]}"
    lead_id = None
    try:
        created = await create_lead_from_openapi(
            db, ctx,
            OpenLeadCreate(
                title=title,
                company_name="UT Co",
                source="test",
                customer_type="终端客户-央企/国企",
            ),
        )
        lead_id = created["id"]
        assert created.get("customer_type") == "terminal_soe"

        row = (
            await db.execute(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == TENANT))
        ).scalar_one()
        assert row.customer_type == "terminal_soe"

        updated = await update_lead_from_openapi(
            db, ctx, lead_id,
            OpenLeadCreate(
                title=title,
                company_name="UT Co",
                source="test",
                customer_type="设计院",
            ),
        )
        assert updated.get("customer_type") == "design_institute"
    finally:
        if lead_id:
            await db.execute(delete(Lead).where(Lead.id == lead_id, Lead.tenant_id == TENANT))
            await db.commit()
