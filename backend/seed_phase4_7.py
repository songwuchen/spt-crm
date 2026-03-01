"""Phase 4-7 incremental seed: adds delivery/payment/change/service permissions."""
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
from app.domains.delivery.models import ErpOrderLink, DeliveryMilestone
from app.domains.payment.models import Invoice, PaymentPlan, PaymentRecord
from app.domains.change.models import ChangeRequest
from app.domains.service_ticket.models import ServiceTicket, RenewalOpportunity

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"

NEW_PERMISSIONS = [
    ("delivery:view", "查看交付", "交付管理"),
    ("delivery:edit", "编辑交付", "交付管理"),
    ("delivery:delete", "删除交付", "交付管理"),
    ("payment:view", "查看回款", "回款管理"),
    ("payment:edit", "编辑回款", "回款管理"),
    ("change:view", "查看变更单", "变更管理"),
    ("change:create", "创建变更单", "变更管理"),
    ("change:edit", "编辑变更单", "变更管理"),
    ("change:delete", "删除变更单", "变更管理"),
    ("service:view", "查看售后工单", "售后管理"),
    ("service:create", "创建售后工单", "售后管理"),
    ("service:edit", "编辑售后工单", "售后管理"),
]

ROLE_PERMS = {
    "tenant_admin": [p[0] for p in NEW_PERMISSIONS],
    "sales_manager": [
        "delivery:view", "delivery:edit", "delivery:delete",
        "payment:view", "payment:edit",
        "change:view", "change:create", "change:edit", "change:delete",
        "service:view", "service:create", "service:edit",
    ],
    "sales_rep": [
        "delivery:view", "delivery:edit",
        "payment:view",
        "change:view", "change:create",
        "service:view", "service:create",
    ],
}


def _id():
    return str(uuid.uuid4())


async def seed():
    async with async_session_factory() as session:
        perm_map = {}
        for code, name, group in NEW_PERMISSIONS:
            existing = (await session.execute(
                select(Permission).where(Permission.code == code)
            )).scalar_one_or_none()
            if existing:
                perm_map[code] = existing.id
                print(f"  Permission '{code}' exists, skipping.")
            else:
                pid = _id()
                perm_map[code] = pid
                session.add(Permission(id=pid, code=code, name=name, group_name=group))
                print(f"  Created permission '{code}'")

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
                if not existing_rp:
                    session.add(RolePermission(
                        id=_id(), tenant_id=DEMO_TENANT_ID,
                        role_id=role.id, permission_id=perm_map[perm_code],
                    ))
                    print(f"  Assigned '{perm_code}' to role '{role_code}'")

        await session.commit()
        print("Phase 4-7 seed completed!")


if __name__ == "__main__":
    asyncio.run(seed())
