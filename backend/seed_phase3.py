"""Phase 3 incremental seed: adds solution permissions to existing roles."""
import asyncio
import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.domains.auth.models import User, Role, Permission, UserRole, RolePermission
from app.domains.tenant.models import PlatformTenant
from app.domains.organization.models import Department, UserDepartment
from app.domains.customer.models import Customer, Contact
from app.domains.lead.models import Lead
from app.domains.attachment.models import Attachment, AttachmentLink
from app.domains.audit.models import AuditLog
from app.domains.project.models import OpportunityProject, ProjectStageHistory
from app.domains.quote.models import Quote, QuoteVersion, QuoteLine
from app.domains.contract.models import Contract, ContractVersion
from app.domains.solution.models import Solution, SolutionVersion

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"

SOLUTION_PERMISSIONS = [
    ("solution:view", "查看方案", "方案管理"),
    ("solution:create", "创建方案", "方案管理"),
    ("solution:edit", "编辑方案", "方案管理"),
    ("solution:delete", "删除方案", "方案管理"),
]

# role_code -> list of permission codes to add
ROLE_PERMS = {
    "tenant_admin": ["solution:view", "solution:create", "solution:edit", "solution:delete"],
    "sales_manager": ["solution:view", "solution:create", "solution:edit", "solution:delete"],
    "sales_rep": ["solution:view", "solution:create", "solution:edit"],
}


def _id():
    return str(uuid.uuid4())


async def seed_phase3():
    async with async_session_factory() as session:
        # 1. Upsert permissions
        perm_map = {}
        for code, name, group in SOLUTION_PERMISSIONS:
            existing = (await session.execute(
                select(Permission).where(Permission.code == code)
            )).scalar_one_or_none()
            if existing:
                perm_map[code] = existing.id
                print(f"  Permission '{code}' already exists, skipping.")
            else:
                pid = _id()
                perm_map[code] = pid
                session.add(Permission(id=pid, code=code, name=name, group_name=group))
                print(f"  Created permission '{code}'")

        # 2. Assign permissions to roles
        for role_code, perm_codes in ROLE_PERMS.items():
            role = (await session.execute(
                select(Role).where(Role.tenant_id == DEMO_TENANT_ID, Role.code == role_code)
            )).scalar_one_or_none()
            if not role:
                print(f"  Role '{role_code}' not found, skipping.")
                continue

            for perm_code in perm_codes:
                existing_rp = (await session.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == perm_map[perm_code],
                    )
                )).scalar_one_or_none()
                if existing_rp:
                    print(f"  Role '{role_code}' already has '{perm_code}', skipping.")
                else:
                    session.add(RolePermission(
                        id=_id(), tenant_id=DEMO_TENANT_ID,
                        role_id=role.id, permission_id=perm_map[perm_code],
                    ))
                    print(f"  Assigned '{perm_code}' to role '{role_code}'")

        await session.commit()
        print("Phase 3 seed completed!")


if __name__ == "__main__":
    asyncio.run(seed_phase3())
