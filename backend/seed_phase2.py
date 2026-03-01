"""Incremental seed: adds Phase 2 permissions and updates roles."""
import asyncio
import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.domains.auth.models import Permission, Role, RolePermission

# Import all models to resolve relationships
from app.domains.tenant.models import PlatformTenant  # noqa: F401
from app.domains.organization.models import Department, UserDepartment  # noqa: F401
from app.domains.customer.models import Customer, Contact  # noqa: F401
from app.domains.lead.models import Lead  # noqa: F401
from app.domains.attachment.models import Attachment, AttachmentLink  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401


def _id():
    return str(uuid.uuid4())


DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"

NEW_PERMISSIONS = [
    ("project:view", "查看商机项目", "商机管理"),
    ("project:create", "创建商机项目", "商机管理"),
    ("project:edit", "编辑商机项目", "商机管理"),
    ("project:delete", "删除商机项目", "商机管理"),
    ("project:advance", "推进/回退阶段", "商机管理"),
    ("quote:view", "查看报价", "报价管理"),
    ("quote:create", "创建报价", "报价管理"),
    ("quote:edit", "编辑报价", "报价管理"),
    ("quote:delete", "删除报价", "报价管理"),
    ("contract:view", "查看合同", "合同管理"),
    ("contract:create", "创建合同", "合同管理"),
    ("contract:edit", "编辑合同", "合同管理"),
    ("contract:delete", "删除合同", "合同管理"),
    ("contract:sign", "签署合同", "合同管理"),
]

# Role -> new permission codes to add
ROLE_NEW_PERMS = {
    "tenant_admin": [p[0] for p in NEW_PERMISSIONS],
    "sales_manager": [
        "project:view", "project:create", "project:edit", "project:advance",
        "quote:view", "quote:create", "quote:edit",
        "contract:view", "contract:create", "contract:edit", "contract:sign",
    ],
    "sales_rep": [
        "project:view", "project:create", "project:edit",
        "quote:view", "quote:create", "quote:edit",
        "contract:view",
    ],
}


async def seed_phase2():
    async with async_session_factory() as session:
        perm_map = {}  # code -> id

        for code, name, group in NEW_PERMISSIONS:
            # Check if already exists
            existing = (await session.execute(
                select(Permission).where(Permission.code == code)
            )).scalar_one_or_none()
            if existing:
                perm_map[code] = existing.id
                print(f"  Permission '{code}' already exists, skipping.")
                continue

            pid = _id()
            perm_map[code] = pid
            session.add(Permission(id=pid, code=code, name=name, group_name=group))
            print(f"  Created permission: {code}")

        await session.commit()

        # Update roles
        for role_code, perm_codes in ROLE_NEW_PERMS.items():
            role = (await session.execute(
                select(Role).where(Role.code == role_code, Role.tenant_id == DEMO_TENANT_ID)
            )).scalar_one_or_none()
            if not role:
                print(f"  Role '{role_code}' not found, skipping.")
                continue

            # Check existing role-permission mappings
            existing_rps = (await session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.tenant_id == DEMO_TENANT_ID,
                )
            )).scalars().all()
            existing_perm_ids = {rp.permission_id for rp in existing_rps}

            added = 0
            for perm_code in perm_codes:
                pid = perm_map.get(perm_code)
                if not pid:
                    continue
                if pid in existing_perm_ids:
                    continue
                session.add(RolePermission(
                    id=_id(), tenant_id=DEMO_TENANT_ID,
                    role_id=role.id, permission_id=pid,
                ))
                added += 1

            print(f"  Role '{role_code}': added {added} new permissions")

        await session.commit()
        print("\nPhase 2 seed completed!")


if __name__ == "__main__":
    asyncio.run(seed_phase2())
