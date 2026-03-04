"""Seed script — populates demo data for development/testing.

Usage:
    cd backend
    python -m scripts.seed
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory, engine, Base, generate_uuid, utcnow
from app.config import settings


TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def seed():
    from sqlalchemy import text, select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if already seeded
        from app.domains.customer.models import Customer
        existing = (await db.execute(
            select(Customer).where(Customer.tenant_id == TENANT_ID).limit(1)
        )).scalar_one_or_none()
        if existing:
            print("Database already has data — skipping seed.")
            return

        # ---- Users (handled by auth seed in conftest, skip here) ----

        # ---- Customers ----
        customers = []
        for i, (name, industry, level) in enumerate([
            ("华锐精密制造", "Machinery", "A"),
            ("中科自动化", "Automation", "A"),
            ("鼎信电子", "Electronics", "B"),
            ("远航新材料", "Materials", "B"),
            ("瑞德工业", "Manufacturing", "C"),
        ]):
            c = Customer(
                id=generate_uuid(), tenant_id=TENANT_ID,
                name=name, industry=industry, level=level,
                source="seed", status="active",
            )
            db.add(c)
            customers.append(c)

        await db.flush()

        # ---- Projects ----
        from app.domains.project.models import OpportunityProject
        projects = []
        stages = ["S1", "S2", "S3", "S4", "S5"]
        amounts = [200000, 500000, 800000, 150000, 1200000]
        for i, cust in enumerate(customers):
            p = OpportunityProject(
                id=generate_uuid(), tenant_id=TENANT_ID,
                name=f"{cust.name}-CRM升级项目",
                customer_id=cust.id,
                stage_code=stages[i % len(stages)],
                amount_expect=amounts[i],
                probability=30 + i * 15,
                status="open",
            )
            db.add(p)
            projects.append(p)

        await db.flush()

        # ---- Stage Gate Config ----
        from app.domains.admin.models import StageGateConfig
        for code, name in [
            ("S1", "线索确认"), ("S2", "需求分析"), ("S3", "方案制定"),
            ("S4", "商务谈判"), ("S5", "合同签订"), ("S6", "交付执行"),
        ]:
            db.add(StageGateConfig(
                id=generate_uuid(), tenant_id=TENANT_ID,
                stage_code=code, name=name, sort_order=int(code[1]),
                gate_rules_json={},
            ))

        # ---- Feature Toggles ----
        from app.domains.admin.models import TenantFeatureToggle
        for code, enabled in [
            ("ai_center", True), ("field_masking", False),
            ("attachment_classification", True), ("webhook_events", True),
        ]:
            db.add(TenantFeatureToggle(
                id=generate_uuid(), tenant_id=TENANT_ID,
                feature_code=code, enabled=enabled,
            ))

        await db.commit()
        print(f"Seeded {len(customers)} customers, {len(projects)} projects, stage configs, feature toggles.")


if __name__ == "__main__":
    asyncio.run(seed())
