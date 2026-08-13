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
        assert first.get("review_status") == "draft"

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


async def test_create_lead_from_openapi_external_reviewed(db):
    """简道云「收录」→ approved 免内审；草稿可晋升为 approved。"""
    from app.domains.openapi.service import normalize_review_status

    assert normalize_review_status("收录") == "approved"
    assert normalize_review_status("袭击") == "attacked"
    assert normalize_review_status("回退") == "rejected"
    assert normalize_review_status("待审") == "draft"
    assert normalize_review_status("approved") == "approved"
    assert normalize_review_status(None) is None

    ctx = _Ctx()
    title = f"LOCAL-LEAD-RV-{uuid.uuid4().hex[:8]}"
    lead_id = None
    try:
        created = await create_lead_from_openapi(
            db, ctx,
            OpenLeadCreate(
                title=title,
                company_name="UT Co",
                source="test",
                review_status="收录",
            ),
        )
        lead_id = created["id"]
        assert created.get("review_status") == "approved"
        # 未传填表人时仍是开放平台占位
        assert created.get("created_by_name") in ("开放平台", None) or created.get("created_by_id") == ctx.app_id

        # 补填表人
        filled = await update_lead_from_openapi(
            db, ctx, lead_id,
            OpenLeadCreate(
                title=title,
                company_name="UT Co",
                source="test",
                review_status="收录",
                created_by_name="岳毅",
                lead_code="申报信息-2026081399999",
            ),
        )
        assert filled.get("created_by_name") == "岳毅"
        assert filled.get("lead_code") == "申报信息-2026081399999"

        # 待审仍草稿
        title2 = f"LOCAL-LEAD-RV2-{uuid.uuid4().hex[:8]}"
        draft = await create_lead_from_openapi(
            db, ctx,
            OpenLeadCreate(title=title2, company_name="UT Co", source="test", review_status="待审"),
        )
        assert draft.get("review_status") == "draft"
        await db.execute(delete(Lead).where(Lead.id == draft["id"], Lead.tenant_id == TENANT))
        await db.commit()

        # 幂等补全：draft → approved
        title3 = f"LOCAL-LEAD-RV3-{uuid.uuid4().hex[:8]}"
        d = await create_lead_from_openapi(
            db, ctx,
            OpenLeadCreate(title=title3, company_name="UT Co", source="test"),
        )
        assert d.get("review_status") == "draft"
        promoted = await update_lead_from_openapi(
            db, ctx, d["id"],
            OpenLeadCreate(title=title3, company_name="UT Co", source="test", review_status="收录"),
        )
        assert promoted.get("review_status") == "approved"
        await db.execute(delete(Lead).where(Lead.id == d["id"], Lead.tenant_id == TENANT))
        await db.commit()
    finally:
        if lead_id:
            await db.execute(delete(Lead).where(Lead.id == lead_id, Lead.tenant_id == TENANT))
            await db.commit()


async def test_create_lead_imports_jdy_flow_history(db):
    """flow_history → 已结束 wf 实例，详情 byBiz 可展示流程动态。"""
    from app.domains.lowcode.workflow_models import WfProcessInstance, WfNodeInstance
    from app.domains.lowcode.workflow_service import find_latest_instance_by_biz
    from app.domains.openapi.schemas import OpenFlowHistoryStep
    from app.domains.openapi.service import _JDY_IMPORT_BIZ_NO, _delete_wf_instance_tree

    ctx = _Ctx()
    title = f"LOCAL-LEAD-FLOW-{uuid.uuid4().hex[:8]}"
    lead_id = None
    try:
        t0 = datetime(2026, 8, 2, 6, 13, 5, tzinfo=timezone.utc)
        t1 = datetime(2026, 8, 2, 6, 13, 6, tzinfo=timezone.utc)
        t2 = datetime(2026, 8, 3, 0, 6, 44, tzinfo=timezone.utc)
        created = await create_lead_from_openapi(
            db, ctx,
            OpenLeadCreate(
                title=title,
                company_name="UT Co",
                source="自报",
                review_status="收录",
                flow_history=[
                    OpenFlowHistoryStep(
                        node_name="递呈信息", handler_name="岳毅",
                        action="提交", started_at=t0, completed_at=t1,
                    ),
                    OpenFlowHistoryStep(
                        node_name="信息情报部审批", handler_name="崔艳丽",
                        action="收录", opinion="同意收录",
                        started_at=t1, completed_at=t2,
                    ),
                ],
            ),
        )
        lead_id = created["id"]
        assert created.get("review_status") == "approved"

        inst = (await db.execute(select(WfProcessInstance).where(
            WfProcessInstance.tenant_id == TENANT,
            WfProcessInstance.biz_type == "lead",
            WfProcessInstance.biz_id == lead_id,
            WfProcessInstance.business_no == _JDY_IMPORT_BIZ_NO,
        ))).scalar_one()
        assert inst.status == "completed"

        nodes = (await db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
        ))).scalars().all()
        names = {n.node_name for n in nodes}
        assert "递呈信息" in names
        assert "信息情报部审批" in names

        detail = await find_latest_instance_by_biz(db, TENANT, "lead", lead_id)
        assert detail is not None
        step_names = [s["node_name"] for s in (detail.get("flow_steps") or [])]
        assert "信息情报部审批" in step_names
        assert "递呈信息" in step_names
    finally:
        if lead_id:
            olds = (await db.execute(select(WfProcessInstance).where(
                WfProcessInstance.tenant_id == TENANT,
                WfProcessInstance.biz_type == "lead",
                WfProcessInstance.biz_id == lead_id,
            ))).scalars().all()
            for old in olds:
                await _delete_wf_instance_tree(db, TENANT, old.id)
            await db.execute(delete(Lead).where(Lead.id == lead_id, Lead.tenant_id == TENANT))
            await db.commit()


async def test_create_lead_from_openapi_uses_pushed_timestamps(db):
    """推送 created_at/updated_at 时覆盖 CRM 系统时间。"""
    ctx = _Ctx()
    title = f"LOCAL-LEAD-TS-{uuid.uuid4().hex[:8]}"
    lead_id = None
    created = datetime(2026, 6, 7, 4, 2, 47, tzinfo=timezone.utc)
    updated = datetime(2026, 6, 8, 10, 0, 0, tzinfo=timezone.utc)
    try:
        dto = await create_lead_from_openapi(
            db, ctx,
            OpenLeadCreate(
                title=title,
                company_name="UT Co",
                source="test",
                created_at=created,
                updated_at=updated,
            ),
        )
        lead_id = dto["id"]
        assert dto.get("created_at", "").startswith("2026-06-07T04:02:47")
        assert dto.get("updated_at", "").startswith("2026-06-08T10:00:00")
        row = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
        assert row.created_at == created
        assert row.updated_at == updated
    finally:
        if lead_id:
            await db.execute(delete(Lead).where(Lead.id == lead_id, Lead.tenant_id == TENANT))
            await db.commit()
