"""Service-level: OpenAPI customer create + customer_code upsert."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.domains.customer.models import Customer
from app.domains.openapi.schemas import OpenCustomerCreate
from app.domains.openapi.service import (
    create_customer_from_openapi,
    update_customer_from_openapi,
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


async def test_create_customer_with_jdy_fields(db):
    ctx = _Ctx()
    code = f"JDY-UT-{uuid.uuid4().hex[:8]}"
    cust_id = None
    try:
        dto = await create_customer_from_openapi(
            db, ctx,
            OpenCustomerCreate(
                name=f"UT客户-{code}",
                customer_code=code,
                short_name="UT短名",
                industry="矿山机械",
                registered_capital="5000.5",
                paid_in_capital="3000",
                founded_year="2010-05-01T00:00:00.000Z",
                is_smart_filing="是",
                is_foreign_trade="否",
                is_company_customer="是",
                customer_nature="民营企业",
                level="B",
                taxpayer_id="91370000MA3XXXXX0X",
                province="山东省",
                city="济南市",
                district="历下区",
                address="山东省济南市历下区某路1号",
                main_products_json="皮带, 托辊",
                source="简道云",
            ),
        )
        cust_id = dto["id"]
        assert dto["customer_code"] == code
        assert dto["registered_capital"] == 5000.5
        assert dto["paid_in_capital"] == 3000.0
        assert dto["founded_year"] == 2010
        assert dto["is_smart_filing"] is True
        assert dto["is_foreign_trade"] is False
        assert dto["is_company_customer"] is True
        assert dto["level"] == "B"
        assert dto["region"] == "山东省济南市历下区"
        assert dto["main_products_json"] == ["皮带", "托辊"]
        assert dto["source"] == "简道云"
    finally:
        if cust_id:
            await db.execute(delete(Customer).where(Customer.id == cust_id, Customer.tenant_id == TENANT))
            await db.commit()


async def test_customer_code_upsert_no_duplicate(db):
    ctx = _Ctx()
    code = f"JDY-UPSERT-{uuid.uuid4().hex[:8]}"
    cust_id = None
    try:
        first = await create_customer_from_openapi(
            db, ctx,
            OpenCustomerCreate(
                name=f"首推-{code}",
                customer_code=code,
                industry="旧行业",
                registered_capital="100",
                source="简道云",
            ),
        )
        cust_id = first["id"]

        second = await create_customer_from_openapi(
            db, ctx,
            OpenCustomerCreate(
                name=f"更新-{code}",
                customer_code=code,
                industry="新行业",
                registered_capital="9999",
                is_smart_filing="是",
                taxpayer_id="TAX-UPDATED",
                source="简道云",
            ),
        )
        assert second["id"] == cust_id
        assert second["name"] == f"更新-{code}"
        assert second["industry"] == "新行业"
        assert second["registered_capital"] == 9999.0
        assert second["is_smart_filing"] is True
        assert second["taxpayer_id"] == "TAX-UPDATED"

        rows = (await db.execute(
            select(Customer).where(
                Customer.tenant_id == TENANT,
                Customer.customer_code == code,
                Customer.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        assert len(rows) == 1
    finally:
        if cust_id:
            await db.execute(delete(Customer).where(Customer.id == cust_id, Customer.tenant_id == TENANT))
            await db.commit()


async def test_update_customer_from_openapi(db):
    ctx = _Ctx()
    code = f"JDY-UPD-{uuid.uuid4().hex[:8]}"
    cust_id = None
    try:
        first = await create_customer_from_openapi(
            db, ctx,
            OpenCustomerCreate(name=f"待补-{code}", customer_code=code, source="简道云"),
        )
        cust_id = first["id"]
        second = await update_customer_from_openapi(
            db, ctx, cust_id,
            OpenCustomerCreate(
                name=f"待补-{code}",
                customer_code=code,
                legal_person="法人甲",
                headcount="120",
                bank_account="工商银行 6222",
                source="简道云",
            ),
        )
        assert second["id"] == cust_id
        assert second["legal_person"] == "法人甲"
        assert second["headcount"] == 120
        assert second["bank_account"] == "工商银行 6222"
        assert second.get("review_status") == "approved"
    finally:
        if cust_id:
            await db.execute(delete(Customer).where(Customer.id == cust_id, Customer.tenant_id == TENANT))
            await db.commit()


async def test_create_customer_imports_jdy_flow_history(db):
    """flow_history → 已结束 customer wf；review_status=approved，不启 CRM 内审。"""
    from datetime import datetime, timezone

    from app.domains.lowcode.workflow_models import WfProcessInstance, WfNodeInstance
    from app.domains.openapi.schemas import OpenFlowHistoryStep
    from app.domains.openapi.service import _JDY_IMPORT_BIZ_NO, _delete_wf_instance_tree

    ctx = _Ctx()
    code = f"JDY-FLOW-{uuid.uuid4().hex[:8]}"
    cust_id = None
    try:
        t0 = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 8, 10, 2, 5, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 8, 10, 3, 0, 0, tzinfo=timezone.utc)
        created = await create_customer_from_openapi(
            db, ctx,
            OpenCustomerCreate(
                name=f"流程客户-{code}",
                customer_code=code,
                source="简道云",
                need_info_distribute="是",
                as_draft=True,
                flow_history=[
                    OpenFlowHistoryStep(
                        node_name="流程发起节点", handler_name="张三",
                        action="提交", started_at=t0, completed_at=t1,
                    ),
                    OpenFlowHistoryStep(
                        node_name="财务审批", handler_name="刘金花",
                        action="通过", opinion="同意建档",
                        started_at=t1, completed_at=t2,
                    ),
                ],
            ),
        )
        cust_id = created["id"]
        assert created.get("review_status") == "approved"
        assert created.get("need_info_distribute") is True
        assert created.get("review_flow_id")

        inst = (await db.execute(select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == TENANT,
            WfProcessInstance.biz_type == "customer",
            WfProcessInstance.biz_id == cust_id,
            WfProcessInstance.business_no == _JDY_IMPORT_BIZ_NO,
        ))).scalar_one()
        assert inst.status == "completed"

        nodes = (await db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
        ))).scalars().all()
        names = {n.node_name for n in nodes}
        assert "流程发起节点" in names
        assert "财务审批" in names
    finally:
        if cust_id:
            # clean imported wf first
            from sqlalchemy import select as sa_select
            rows = (await db.execute(sa_select(WfProcessInstance).where(
                WfProcessInstance.tenant_id == TENANT,
                WfProcessInstance.biz_type == "customer",
                WfProcessInstance.biz_id == cust_id,
            ))).scalars().all()
            for row in rows:
                await _delete_wf_instance_tree(db, TENANT, row.id)
            await db.execute(delete(Customer).where(Customer.id == cust_id, Customer.tenant_id == TENANT))
            await db.commit()
