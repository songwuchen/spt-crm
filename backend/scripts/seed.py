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

        # Permissions — complete list matching all require_permissions() in routers
        perm_codes = [
            ("customer:view", "查看客户", "客户"),
            ("customer:create", "创建客户", "客户"),
            ("customer:edit", "编辑客户", "客户"),
            ("customer:delete", "删除客户", "客户"),
            ("contact:view", "查看联系人", "联系人"),
            ("contact:create", "创建联系人", "联系人"),
            ("contact:edit", "编辑联系人", "联系人"),
            ("contact:delete", "删除联系人", "联系人"),
            ("lead:view", "查看线索", "线索"),
            ("lead:create", "创建线索", "线索"),
            ("lead:edit", "编辑线索", "线索"),
            ("lead:delete", "删除线索", "线索"),
            ("lead:qualify", "转化线索", "线索"),
            ("lead:discard", "废弃线索", "线索"),
            ("project:view", "查看商机", "商机"),
            ("project:create", "创建商机", "商机"),
            ("project:edit", "编辑商机", "商机"),
            ("project:delete", "删除商机", "商机"),
            ("project:advance", "推进商机阶段", "商机"),
            ("quote:view", "查看报价", "报价"),
            ("quote:create", "创建报价", "报价"),
            ("quote:edit", "编辑报价", "报价"),
            ("quote:delete", "删除报价", "报价"),
            ("contract:view", "查看合同", "合同"),
            ("contract:create", "创建合同", "合同"),
            ("contract:edit", "编辑合同", "合同"),
            ("contract:delete", "删除合同", "合同"),
            ("contract:sign", "签署合同", "合同"),
            ("solution:view", "查看方案", "方案"),
            ("solution:create", "创建方案", "方案"),
            ("solution:edit", "编辑方案", "方案"),
            ("solution:delete", "删除方案", "方案"),
            ("delivery:view", "查看交付", "交付"),
            ("delivery:edit", "编辑交付", "交付"),
            ("delivery:delete", "删除交付", "交付"),
            ("payment:view", "查看回款", "回款"),
            ("payment:edit", "编辑回款", "回款"),
            ("change:view", "查看变更", "变更"),
            ("change:create", "创建变更", "变更"),
            ("change:edit", "编辑变更", "变更"),
            ("change:delete", "删除变更", "变更"),
            ("service:view", "查看工单", "工单"),
            ("service:create", "创建工单", "工单"),
            ("service:edit", "编辑工单", "工单"),
            ("service:delete", "删除工单", "工单"),
            ("approval:view", "查看审批", "审批"),
            ("approval:approve", "审批操作", "审批"),
            ("approval:decide", "审批决定", "审批"),
            ("approval:delegate", "委托审批", "审批"),
            ("approval:withdraw", "撤回审批", "审批"),
            ("approval:resubmit", "重新提交审批", "审批"),
            ("approval:manage", "管理审批", "审批"),
            ("attachment:upload", "上传附件", "附件"),
            ("attachment:download", "下载附件", "附件"),
            ("audit:view", "查看审计", "审计"),
            ("role:view", "查看角色", "系统"),
            ("role:edit", "编辑角色", "系统"),
            ("role:manage", "管理角色", "系统"),
            ("user:view", "查看用户", "系统"),
            ("user:manage", "管理用户", "系统"),
            ("dept:view", "查看部门", "组织"),
            ("dept:manage", "管理部门", "组织"),
            ("tenant:view", "查看租户", "平台"),
            ("tenant:manage", "管理租户", "平台"),
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
                project_code=f"PRJ-SEED-{i+1:04d}",
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

        # ---- Stage Definitions ----
        from app.domains.admin.models import StageDefinition
        for code, name in [
            ("S1", "线索确认"), ("S2", "需求分析"), ("S3", "方案制定"),
            ("S4", "商务谈判"), ("S5", "合同签订"), ("S6", "交付执行"),
        ]:
            db.add(StageDefinition(
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
