"""Seed script: creates default permissions, roles, demo tenant, and admin user."""
import asyncio
import uuid

import bcrypt
from sqlalchemy import select

from app.database import async_session_factory, engine, Base, TenantScopedBase, PlatformBase
from app.domains.auth.models import User, Role, Permission, UserRole, RolePermission
from app.domains.tenant.models import PlatformTenant
from app.domains.organization.models import Department

# Import all models to register metadata
from app.domains.customer.models import Customer, Contact
from app.domains.lead.models import Lead
from app.domains.attachment.models import Attachment, AttachmentLink
from app.domains.audit.models import AuditLog
from app.domains.project.models import OpportunityProject, ProjectStageHistory
from app.domains.quote.models import Quote, QuoteVersion, QuoteLine
from app.domains.contract.models import Contract, ContractVersion
from app.domains.solution.models import Solution, SolutionVersion
from app.domains.delivery.models import ErpOrderLink, DeliveryMilestone
from app.domains.payment.models import Invoice, PaymentPlan, PaymentRecord
from app.domains.change.models import ChangeRequest
from app.domains.service_ticket.models import ServiceTicket, RenewalOpportunity


def _id():
    return str(uuid.uuid4())


# ---- Default permissions ----
PERMISSIONS = [
    # Customer
    ("customer:view", "查看客户", "客户管理"),
    ("customer:create", "创建客户", "客户管理"),
    ("customer:edit", "编辑客户", "客户管理"),
    ("customer:delete", "删除客户", "客户管理"),
    # Contact
    ("contact:view", "查看联系人", "客户管理"),
    ("contact:create", "创建联系人", "客户管理"),
    ("contact:edit", "编辑联系人", "客户管理"),
    ("contact:delete", "删除联系人", "客户管理"),
    # Lead
    ("lead:view", "查看线索", "线索管理"),
    ("lead:create", "创建线索", "线索管理"),
    ("lead:edit", "编辑线索", "线索管理"),
    ("lead:delete", "删除线索", "线索管理"),
    ("lead:qualify", "转化线索", "线索管理"),
    ("lead:discard", "废弃线索", "线索管理"),
    # Organization
    ("dept:view", "查看部门", "组织管理"),
    ("dept:manage", "管理部门", "组织管理"),
    ("user:view", "查看用户", "组织管理"),
    ("user:manage", "管理用户", "组织管理"),
    ("role:view", "查看角色", "组织管理"),
    ("role:manage", "管理角色", "组织管理"),
    # Attachment
    ("attachment:upload", "上传附件", "附件管理"),
    ("attachment:download", "下载附件", "附件管理"),
    # Project
    ("project:view", "查看商机项目", "商机管理"),
    ("project:create", "创建商机项目", "商机管理"),
    ("project:edit", "编辑商机项目", "商机管理"),
    ("project:delete", "删除商机项目", "商机管理"),
    ("project:advance", "推进/回退阶段", "商机管理"),
    # Quote
    ("quote:view", "查看报价", "报价管理"),
    ("quote:create", "创建报价", "报价管理"),
    ("quote:edit", "编辑报价", "报价管理"),
    ("quote:delete", "删除报价", "报价管理"),
    # Contract
    ("contract:view", "查看合同", "合同管理"),
    ("contract:create", "创建合同", "合同管理"),
    ("contract:edit", "编辑合同", "合同管理"),
    ("contract:delete", "删除合同", "合同管理"),
    ("contract:sign", "签署合同", "合同管理"),
    # Solution
    ("solution:view", "查看方案", "方案管理"),
    ("solution:create", "创建方案", "方案管理"),
    ("solution:edit", "编辑方案", "方案管理"),
    ("solution:delete", "删除方案", "方案管理"),
    # Delivery
    ("delivery:view", "查看交付", "交付管理"),
    ("delivery:edit", "编辑交付", "交付管理"),
    ("delivery:delete", "删除交付", "交付管理"),
    # Payment
    ("payment:view", "查看回款", "回款管理"),
    ("payment:edit", "编辑回款", "回款管理"),
    # Change
    ("change:view", "查看变更单", "变更管理"),
    ("change:create", "创建变更单", "变更管理"),
    ("change:edit", "编辑变更单", "变更管理"),
    ("change:delete", "删除变更单", "变更管理"),
    # Service
    ("service:view", "查看售后工单", "售后管理"),
    ("service:create", "创建售后工单", "售后管理"),
    ("service:edit", "编辑售后工单", "售后管理"),
    # Audit
    ("audit:view", "查看审计日志", "审计管理"),
    # Data scope
    ("data:view_all", "查看全部数据", "数据权限"),
    # Tenant (platform level)
    ("tenant:view", "查看租户", "平台管理"),
    ("tenant:manage", "管理租户", "平台管理"),
]

# Roles and their permission codes
ROLES = {
    "tenant_admin": {
        "name": "租户管理员",
        "description": "租户内全部权限",
        "is_system": True,
        "permissions": [p[0] for p in PERMISSIONS if not p[0].startswith("tenant:")],
    },
    "sales_manager": {
        "name": "销售经理",
        "description": "客户、线索、商机、报价、合同管理",
        "is_system": True,
        "permissions": [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit", "lead:qualify", "lead:discard",
            "project:view", "project:create", "project:edit", "project:advance",
            "quote:view", "quote:create", "quote:edit",
            "contract:view", "contract:create", "contract:edit", "contract:sign",
            "solution:view", "solution:create", "solution:edit", "solution:delete",
            "delivery:view", "delivery:edit", "delivery:delete",
            "payment:view", "payment:edit",
            "change:view", "change:create", "change:edit", "change:delete",
            "service:view", "service:create", "service:edit",
            "attachment:upload", "attachment:download",
            "data:view_all",
        ],
    },
    "sales_rep": {
        "name": "销售代表",
        "description": "基础客户、线索和商机操作",
        "is_system": True,
        "permissions": [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit",
            "project:view", "project:create", "project:edit",
            "quote:view", "quote:create", "quote:edit",
            "solution:view", "solution:create", "solution:edit",
            "delivery:view", "delivery:edit",
            "payment:view",
            "change:view", "change:create",
            "service:view", "service:create",
            "contract:view",
            "attachment:upload", "attachment:download",
        ],
    },
}

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEMO_ADMIN_ID = "00000000-0000-0000-0000-000000000010"
DEMO_DEPT_ID = "00000000-0000-0000-0000-000000000020"


async def seed():
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Check if already seeded
        existing = (await session.execute(select(PlatformTenant).where(PlatformTenant.id == DEMO_TENANT_ID))).scalar()
        if existing:
            print("Seed data already exists, skipping.")
            return

        # 1. Create permissions
        perm_map = {}  # code -> id
        for code, name, group in PERMISSIONS:
            pid = _id()
            perm_map[code] = pid
            session.add(Permission(id=pid, code=code, name=name, group_name=group))

        # 2. Create demo tenant
        session.add(PlatformTenant(
            id=DEMO_TENANT_ID,
            name="演示租户",
            code="demo",
            plan="pro",
            is_active=True,
            contact_name="管理员",
            contact_email="admin@demo.com",
        ))

        # 3. Create roles for demo tenant
        role_map = {}  # code -> id
        for code, info in ROLES.items():
            rid = _id()
            role_map[code] = rid
            session.add(Role(
                id=rid, tenant_id=DEMO_TENANT_ID,
                code=code, name=info["name"],
                description=info["description"], is_system=info["is_system"],
            ))
            # Role-permission mapping
            for perm_code in info["permissions"]:
                session.add(RolePermission(
                    id=_id(), tenant_id=DEMO_TENANT_ID,
                    role_id=rid, permission_id=perm_map[perm_code],
                ))

        # 4. Create admin user
        session.add(User(
            id=DEMO_ADMIN_ID,
            tenant_id=DEMO_TENANT_ID,
            username="admin",
            password_hash=bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
            real_name="系统管理员",
            email="admin@demo.com",
            is_active=True,
        ))

        # 5. Assign tenant_admin role to admin
        session.add(UserRole(
            id=_id(), tenant_id=DEMO_TENANT_ID,
            user_id=DEMO_ADMIN_ID, role_id=role_map["tenant_admin"],
        ))

        # 6. Create root department
        session.add(Department(
            id=DEMO_DEPT_ID,
            tenant_id=DEMO_TENANT_ID,
            name="演示租户",
            parent_id=None,
            path="/",
            sort_order=0,
        ))

        await session.commit()
        print("Seed data created successfully!")
        print("  Tenant: demo (演示租户)")
        print("  Admin: admin / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
