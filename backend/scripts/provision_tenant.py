"""Provision a new tenant (idempotent).

Creates a usable tenant: platform_tenants record + admin role (all permissions)
+ admin user + S1-S6 stage definitions + default feature toggles.

Run INSIDE the backend container:
    docker exec -e TENANT_NAME=小威环境 -e TENANT_CODE=xiaowei \
                -e ADMIN_USERNAME=xiaowei -e ADMIN_PASSWORD=*** \
                ai-crm-backend-1 python -m scripts.provision_tenant

Idempotent: if the tenant code already exists it only fills in any missing
admin role / permissions / user / stages / toggles, never duplicating.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory, engine, Base, generate_uuid  # noqa: E402

# Import models so the SQLAlchemy registry is complete
import app.domains.auth.models  # noqa: F401,E402
import app.domains.organization.models  # noqa: F401,E402
import app.domains.admin.models  # noqa: F401,E402
import app.domains.tenant.models  # noqa: F401,E402


async def provision():
    from sqlalchemy import select
    import bcrypt
    from app.domains.tenant.models import PlatformTenant
    from app.domains.auth.models import User, Role, Permission, UserRole, RolePermission
    from app.domains.admin.models import StageDefinition, TenantFeatureToggle

    name = os.environ["TENANT_NAME"]
    code = os.environ["TENANT_CODE"]
    admin_username = os.environ["ADMIN_USERNAME"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    admin_realname = os.environ.get("ADMIN_REALNAME", name + "管理员")
    plan = os.environ.get("TENANT_PLAN", "free")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        report = {}

        # 1) Platform tenant record
        tenant = (await db.execute(
            select(PlatformTenant).where(PlatformTenant.code == code)
        )).scalar_one_or_none()
        if tenant is None:
            tenant = PlatformTenant(id=generate_uuid(), name=name, code=code, plan=plan, is_active=True)
            db.add(tenant)
            await db.flush()
            report["tenant"] = f"created {code} ({tenant.id})"
        else:
            report["tenant"] = f"exists {code} ({tenant.id})"
        tenant_id = tenant.id

        # 2) Admin role for this tenant
        admin_role = (await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == "admin")
        )).scalar_one_or_none()
        if admin_role is None:
            admin_role = Role(id=generate_uuid(), tenant_id=tenant_id, code="admin",
                              name="系统管理员", description="拥有全部权限", is_system=True, data_scope="all")
            db.add(admin_role)
            await db.flush()
            report["admin_role"] = "created"
        else:
            report["admin_role"] = "exists"

        # 3) Grant ALL global permissions to the admin role (additive)
        all_perms = (await db.execute(select(Permission))).scalars().all()
        existing_rp = {rp.permission_id for rp in (await db.execute(
            select(RolePermission).where(
                RolePermission.tenant_id == tenant_id, RolePermission.role_id == admin_role.id)
        )).scalars().all()}
        granted = 0
        for p in all_perms:
            if p.id in existing_rp:
                continue
            db.add(RolePermission(id=generate_uuid(), tenant_id=tenant_id,
                                  role_id=admin_role.id, permission_id=p.id))
            granted += 1
        report["permissions_granted"] = f"{granted} (total {len(all_perms)})"

        # 4) Admin user (scoped unique by tenant; don't reset if exists)
        admin = (await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == admin_username)
        )).scalar_one_or_none()
        if admin is None:
            admin = User(
                id=generate_uuid(), tenant_id=tenant_id, username=admin_username,
                password_hash=bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode(),
                real_name=admin_realname, is_active=True,
            )
            db.add(admin)
            await db.flush()
            report["admin_user"] = f"created {admin_username}"
        else:
            report["admin_user"] = f"exists {admin_username} (password unchanged)"

        # 5) User-role link
        ur = (await db.execute(
            select(UserRole).where(UserRole.user_id == admin.id, UserRole.role_id == admin_role.id)
        )).scalar_one_or_none()
        if ur is None:
            db.add(UserRole(id=generate_uuid(), tenant_id=tenant_id, user_id=admin.id, role_id=admin_role.id))
            report["user_role"] = "linked"
        else:
            report["user_role"] = "exists"

        # 6) Stage definitions S1-S6
        existing_stages = {s.stage_code for s in (await db.execute(
            select(StageDefinition).where(StageDefinition.tenant_id == tenant_id)
        )).scalars().all()}
        stages_added = 0
        for sc, sn in [("S1", "线索确认"), ("S2", "需求分析"), ("S3", "方案制定"),
                       ("S4", "商务谈判"), ("S5", "合同签订"), ("S6", "交付执行")]:
            if sc in existing_stages:
                continue
            db.add(StageDefinition(id=generate_uuid(), tenant_id=tenant_id, stage_code=sc,
                                   name=sn, sort_order=int(sc[1]), gate_rules_json={}))
            stages_added += 1
        report["stages_added"] = stages_added

        # 7) Feature toggles
        existing_toggles = {t.feature_code for t in (await db.execute(
            select(TenantFeatureToggle).where(TenantFeatureToggle.tenant_id == tenant_id)
        )).scalars().all()}
        toggles_added = 0
        for fc, en in [("ai_center", True), ("field_masking", False),
                       ("attachment_classification", True), ("webhook_events", True)]:
            if fc in existing_toggles:
                continue
            db.add(TenantFeatureToggle(id=generate_uuid(), tenant_id=tenant_id, feature_code=fc, enabled=en))
            toggles_added += 1
        report["toggles_added"] = toggles_added

        await db.commit()

        print("=== Tenant provisioning complete ===")
        for k, v in report.items():
            print(f"  {k:20s}: {v}")
        print(f"  login              : username={admin_username}  tenant_code={code}")


if __name__ == "__main__":
    asyncio.run(provision())
