"""Service-level local regression: OpenAPI contract upsert by contract_no.

Bypasses HTTP login (local DB admin password may differ from seed default) and
exercises create_contract_from_openapi against the real Postgres used by docker.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import generate_uuid
from app.domains.customer.models import Customer
from app.domains.contract.models import Contract, ContractVersion
from app.domains.openapi.schemas import OpenContractCreate
from app.domains.openapi.service import create_contract_from_openapi
from sqlalchemy import select, delete


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


async def test_create_contract_upsert_by_no_and_allows_negative(db):
    ctx = _Ctx()
    contract_no = f"LOCAL-UT-{uuid.uuid4().hex[:10].upper()}"
    customer = Customer(
        id=generate_uuid(),
        tenant_id=TENANT,
        name=f"Local Upsert {contract_no}",
        source="test",
        status="active",
        is_deleted=False,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    contract_id = None

    try:
        first = await create_contract_from_openapi(
            db, ctx,
            OpenContractCreate(
                customer_id=customer.id,
                contract_no=contract_no,
                title="初版",
                amount_total=14700,
                status="draft",
                custom_fields={"region": "华北"},
            ),
        )
        assert first["contract_no"] == contract_no
        assert float(first["amount_total"]) == 14700
        contract_id = first["id"]

        # Same no, different amount (incl. negative 变动) → update, not IntegrityError/500.
        second = await create_contract_from_openapi(
            db, ctx,
            OpenContractCreate(
                customer_id=customer.id,
                contract_no=contract_no,
                title="变动后",
                amount_total=-80000,
                status="draft",
                custom_fields={"region": "西北", "contract_status_raw": "变动"},
            ),
        )
        assert second["id"] == contract_id
        assert float(second["amount_total"]) == -80000
        assert (second.get("custom_fields") or {}).get("region") == "西北"

        rows = (await db.execute(
            select(Contract).where(
                Contract.tenant_id == TENANT,
                Contract.contract_no == contract_no,
            )
        )).scalars().all()
        assert len(rows) == 1, f"expected single row after upsert, got {len(rows)}"
        assert float(rows[0].amount_total) == -80000
    finally:
        if contract_id:
            await db.execute(delete(ContractVersion).where(
                ContractVersion.contract_id == contract_id, ContractVersion.tenant_id == TENANT,
            ))
            await db.execute(delete(Contract).where(Contract.id == contract_id))
        else:
            await db.execute(delete(Contract).where(
                Contract.contract_no == contract_no, Contract.tenant_id == TENANT,
            ))
        await db.execute(delete(Customer).where(Customer.id == customer.id))
        await db.commit()
