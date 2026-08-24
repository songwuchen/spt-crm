"""OpenAPI contract created_by maps from 简道云提交人 (not 开放平台)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import generate_uuid
from app.domains.auth.models import User
from app.domains.organization.models import UserDepartment  # noqa: F401 — mapper deps
from app.domains.contract.models import Contract, ContractVersion
from app.domains.customer.models import Customer
from app.domains.openapi.schemas import OpenContractCreate
from app.domains.openapi.service import (
    _person_display_from_reg_value,
    create_contract_from_openapi,
)


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


def test_person_display_from_reg_value():
    assert _person_display_from_reg_value("张玲玉") == "张玲玉"
    assert _person_display_from_reg_value({"name": "张玲玉"}) == "张玲玉"
    assert _person_display_from_reg_value([{"name": "张玲玉", "username": "u1"}]) == "张玲玉"
    assert _person_display_from_reg_value(None) is None
    assert _person_display_from_reg_value([]) is None
    assert _person_display_from_reg_value("  ") is None


async def test_create_contract_uses_submitter_as_created_by(db):
    ctx = _Ctx()
    suffix = uuid.uuid4().hex[:10].upper()
    contract_no = f"LOCAL-CB-{suffix}"
    real_name = f"提交人UT{suffix[:6]}"
    customer = Customer(
        id=generate_uuid(),
        tenant_id=TENANT,
        name=f"CB Cust {contract_no}",
        source="test",
        status="active",
        is_deleted=False,
    )
    user = User(
        id=generate_uuid(),
        tenant_id=TENANT,
        username=f"ut_cb_{suffix.lower()}",
        real_name=real_name,
        password_hash="x",
        is_active=True,
    )
    db.add(customer)
    db.add(user)
    await db.commit()
    await db.refresh(customer)
    await db.refresh(user)
    contract_id = None

    try:
        dto = await create_contract_from_openapi(
            db, ctx,
            OpenContractCreate(
                customer_id=customer.id,
                contract_no=contract_no,
                title="提交人映射",
                amount_total=100,
                status="draft",
                registration_json={"submitter": real_name, "serial_no": "S1"},
            ),
        )
        contract_id = dto["id"]
        row = (await db.execute(
            select(Contract).where(Contract.id == contract_id)
        )).scalar_one()
        assert row.created_by_name == real_name
        assert row.created_by_id == user.id
        assert row.created_by_name != "开放平台"
        assert row.created_by_id != ctx.app_id

        # upsert 幂等：仍保持提交人，不回退开放平台
        await create_contract_from_openapi(
            db, ctx,
            OpenContractCreate(
                customer_id=customer.id,
                contract_no=contract_no,
                title="提交人映射-改",
                amount_total=200,
                status="draft",
                registration_json={"submitter": real_name},
            ),
        )
        await db.refresh(row)
        assert row.created_by_id == user.id
        assert row.created_by_name == real_name
        assert float(row.amount_total) == 200
    finally:
        if contract_id:
            await db.execute(delete(ContractVersion).where(
                ContractVersion.contract_id == contract_id, ContractVersion.tenant_id == TENANT,
            ))
            await db.execute(delete(Contract).where(Contract.id == contract_id))
        await db.execute(delete(Customer).where(Customer.id == customer.id))
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()


async def test_create_contract_uses_top_level_created_by_name(db):
    ctx = _Ctx()
    suffix = uuid.uuid4().hex[:10].upper()
    contract_no = f"LOCAL-CB2-{suffix}"
    name = f"顶栏提交人{suffix[:6]}"
    customer = Customer(
        id=generate_uuid(),
        tenant_id=TENANT,
        name=f"CB2 Cust {contract_no}",
        source="test",
        status="active",
        is_deleted=False,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    contract_id = None
    try:
        dto = await create_contract_from_openapi(
            db, ctx,
            OpenContractCreate(
                customer_id=customer.id,
                contract_no=contract_no,
                title="顶栏",
                amount_total=1,
                status="draft",
                created_by_name=name,
            ),
        )
        contract_id = dto["id"]
        row = (await db.execute(
            select(Contract).where(Contract.id == contract_id)
        )).scalar_one()
        # 姓名保留，即使 CRM 无对应用户
        assert row.created_by_name == name
        assert row.created_by_id is None
    finally:
        if contract_id:
            await db.execute(delete(ContractVersion).where(
                ContractVersion.contract_id == contract_id, ContractVersion.tenant_id == TENANT,
            ))
            await db.execute(delete(Contract).where(Contract.id == contract_id))
        await db.execute(delete(Customer).where(Customer.id == customer.id))
        await db.commit()
