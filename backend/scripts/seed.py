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

# Import all models so SQLAlchemy relationship registry is complete
import app.domains.auth.models  # noqa: F401
import app.domains.organization.models  # noqa: F401
import app.domains.customer.models  # noqa: F401
import app.domains.project.models  # noqa: F401
import app.domains.admin.models  # noqa: F401


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

        # ---- Admin User + Role + Permissions ----
        import bcrypt
        from app.domains.auth.models import User, Role, Permission, UserRole, RolePermission

        admin_user_id = "00000000-0000-0000-0000-000000000010"
        admin_role_id = generate_uuid()

        # Permissions
        perm_codes = [
            ("customer:view", "查看客户", "客户"),
            ("customer:edit", "编辑客户", "客户"),
            ("lead:view", "查看线索", "线索"),
            ("lead:edit", "编辑线索", "线索"),
            ("project:view", "查看商机", "商机"),
            ("project:edit", "编辑商机", "商机"),
            ("quote:view", "查看报价", "报价"),
            ("quote:edit", "编辑报价", "报价"),
            ("contract:view", "查看合同", "合同"),
            ("contract:edit", "编辑合同", "合同"),
            ("payment:view", "查看回款", "回款"),
            ("payment:edit", "编辑回款", "回款"),
            ("change:view", "查看变更", "变更"),
            ("change:edit", "编辑变更", "变更"),
            ("approval:view", "查看审批", "审批"),
            ("approval:manage", "管理审批", "审批"),
            ("audit:view", "查看审计", "审计"),
            ("audit:export", "导出审计", "审计"),
            ("role:manage", "管理角色", "系统"),
            ("dashboard:view", "查看工作台", "工作台"),
            ("ai:use", "使用AI", "AI"),
            ("notification:view", "查看通知", "通知"),
        ]
        perm_ids = {}
        for code, name, group in perm_codes:
            pid = generate_uuid()
            db.add(Permission(id=pid, code=code, name=name, group_name=group))
            perm_ids[code] = pid

        # Admin role with all permissions
        db.add(Role(
            id=admin_role_id, tenant_id=TENANT_ID,
            code="admin", name="系统管理员", description="拥有全部权限", is_system=True,
        ))
        await db.flush()

        for code, pid in perm_ids.items():
            db.add(RolePermission(
                id=generate_uuid(), tenant_id=TENANT_ID,
                role_id=admin_role_id, permission_id=pid,
            ))

        # Admin user
        hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        db.add(User(
            id=admin_user_id, tenant_id=TENANT_ID,
            username="admin", password_hash=hashed,
            real_name="管理员", is_active=True,
        ))
        await db.flush()

        db.add(UserRole(
            id=generate_uuid(), tenant_id=TENANT_ID,
            user_id=admin_user_id, role_id=admin_role_id,
        ))
        await db.flush()

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
