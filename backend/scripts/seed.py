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


async def seed(include_demo: bool = True):
    # Per-row upsert. Safe to re-run on every deploy: missing permissions, roles,
    # demo customers / projects / stages / feature toggles are added; existing rows
    # are left alone (so operator edits — passwords, customized stage gates,
    # toggle states, real customer data sharing a demo name — are not clobbered).
    #
    # include_demo=False (production installs): seed permissions / roles / admin /
    # stage defs / toggles / default approval policies, but SKIP the fake demo
    # customers & projects. Real customer deployments call this via deploy.sh.
    from sqlalchemy import select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        import bcrypt
        from app.domains.customer.models import Customer
        from app.domains.auth.models import User, Role, Permission, UserRole, RolePermission

        added = {"permissions": 0, "perm_updates": 0, "roles": 0, "role_perms": 0,
                 "users": 0, "user_roles": 0, "customers": 0, "projects": 0,
                 "stages": 0, "feature_toggles": 0, "approval_policies": 0}

        admin_user_id = "00000000-0000-0000-0000-000000000010"

        # Permission catalog — single source of truth (shared with the admin
        # 「同步标准角色与权限」API and scripts/seed_function_roles.py).
        from app.common.rbac_catalog import PERMISSIONS as perm_codes

        # ---- Permissions (global, keyed by code) ----
        existing_perms = {p.code: p for p in (await db.execute(select(Permission))).scalars().all()}
        for code, name, group in perm_codes:
            perm = existing_perms.get(code)
            if perm is None:
                perm = Permission(id=generate_uuid(), code=code, name=name, group_name=group)
                db.add(perm)
                existing_perms[code] = perm
                added["permissions"] += 1
            elif perm.name != name or perm.group_name != group:
                perm.name = name
                perm.group_name = group
                added["perm_updates"] += 1
        await db.flush()

        # ---- Admin role (per tenant, keyed by tenant_id + code) ----
        admin_role = (await db.execute(
            select(Role).where(Role.tenant_id == TENANT_ID, Role.code == "admin")
        )).scalar_one_or_none()
        if admin_role is None:
            admin_role = Role(
                id=generate_uuid(), tenant_id=TENANT_ID,
                code="admin", name="系统管理员", description="拥有全部权限", is_system=True,
            )
            db.add(admin_role)
            added["roles"] += 1
        await db.flush()

        # ---- Role permissions: 给「所有租户」的 admin 角色补齐全部全局权限 ----
        # admin 角色定义即"拥有全部权限"。升级新增权限后,若只给 demo 租户补授,
        # 其它客户(如已开通的老租户)的 admin 角色就缺新权限,新功能菜单/接口因权限
        # 过滤而"看不到/无权限"。这里遍历所有 code=="admin" 的角色做增量补授(不动
        # 已有授权、不影响自定义受限角色),保证每次部署后各客户 admin 权限自动完整。
        all_perms = list(existing_perms.values())
        admin_roles = (await db.execute(
            select(Role).where(Role.code == "admin")
        )).scalars().all()
        for role in admin_roles:
            granted = {rp.permission_id for rp in (await db.execute(
                select(RolePermission).where(
                    RolePermission.tenant_id == role.tenant_id,
                    RolePermission.role_id == role.id,
                )
            )).scalars().all()}
            for perm in all_perms:
                if perm.id in granted:
                    continue
                db.add(RolePermission(
                    id=generate_uuid(), tenant_id=role.tenant_id,
                    role_id=role.id, permission_id=perm.id,
                ))
                granted.add(perm.id)
                added["role_perms"] += 1

        # ---- Admin user (don't reset password if exists) ----
        admin = (await db.execute(
            select(User).where(User.id == admin_user_id)
        )).scalar_one_or_none()
        if admin is None:
            db.add(User(
                id=admin_user_id, tenant_id=TENANT_ID,
                username="admin",
                password_hash=bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
                real_name="管理员", is_active=True,
            ))
            added["users"] += 1
        await db.flush()

        # ---- User-role assignment ----
        ur_exists = (await db.execute(
            select(UserRole).where(
                UserRole.user_id == admin_user_id,
                UserRole.role_id == admin_role.id,
            )
        )).scalar_one_or_none()
        if ur_exists is None:
            db.add(UserRole(
                id=generate_uuid(), tenant_id=TENANT_ID,
                user_id=admin_user_id, role_id=admin_role.id,
            ))
            added["user_roles"] += 1
        await db.flush()

        # ---- Demo customers (keyed by tenant + name + source='seed' so we never
        # confuse demo data with real customers an operator may have created) ----
        demo_customers = [
            ("华锐精密制造", "Machinery", "A"),
            ("中科自动化", "Automation", "A"),
            ("鼎信电子", "Electronics", "B"),
            ("远航新材料", "Materials", "B"),
            ("瑞德工业", "Manufacturing", "C"),
        ] if include_demo else []  # 生产安装(include_demo=False)不注入演示客户/项目
        existing_demo = {c.name: c for c in (await db.execute(
            select(Customer).where(
                Customer.tenant_id == TENANT_ID,
                Customer.source == "seed",
            )
        )).scalars().all()}
        customers = []
        for name, industry, level in demo_customers:
            cust = existing_demo.get(name)
            if cust is None:
                cust = Customer(
                    id=generate_uuid(), tenant_id=TENANT_ID,
                    name=name, industry=industry, level=level,
                    source="seed", status="active",
                )
                db.add(cust)
                added["customers"] += 1
            customers.append(cust)
        await db.flush()

        # ---- Demo projects (keyed by project_code) ----
        from app.domains.project.models import OpportunityProject
        stages_seq = ["S1", "S2", "S3", "S4", "S5"]
        amounts = [200000, 500000, 800000, 150000, 1200000]
        existing_projects = {p.project_code for p in (await db.execute(
            select(OpportunityProject).where(
                OpportunityProject.tenant_id == TENANT_ID,
                OpportunityProject.project_code.like("PRJ-SEED-%"),
            )
        )).scalars().all()}
        for i, cust in enumerate(customers):
            code = f"PRJ-SEED-{i+1:04d}"
            if code in existing_projects:
                continue
            db.add(OpportunityProject(
                id=generate_uuid(), tenant_id=TENANT_ID,
                project_code=code, name=f"{cust.name}-CRM升级项目",
                customer_id=cust.id,
                stage_code=stages_seq[i % len(stages_seq)],
                amount_expect=amounts[i], probability=30 + i * 15,
                status="open",
            ))
            added["projects"] += 1

        # ---- Stage Definitions (keyed by tenant_id + stage_code) ----
        from app.domains.admin.models import StageDefinition
        existing_stages = {s.stage_code for s in (await db.execute(
            select(StageDefinition).where(StageDefinition.tenant_id == TENANT_ID)
        )).scalars().all()}
        for code, name in [
            ("S1", "线索确认"), ("S2", "需求分析"), ("S3", "方案报价"),
            ("S4", "商务谈判"), ("S5", "合同签订"), ("S6", "交付验收"),
        ]:
            if code in existing_stages:
                continue
            db.add(StageDefinition(
                id=generate_uuid(), tenant_id=TENANT_ID,
                stage_code=code, name=name, sort_order=int(code[1]),
                gate_rules_json={},
            ))
            added["stages"] += 1

        # ---- Feature Toggles (keyed by tenant_id + feature_code) ----
        # Don't overwrite — operator may have flipped a toggle deliberately.
        from app.domains.admin.models import TenantFeatureToggle
        existing_toggles = {t.feature_code for t in (await db.execute(
            select(TenantFeatureToggle).where(TenantFeatureToggle.tenant_id == TENANT_ID)
        )).scalars().all()}
        for code, enabled in [
            ("ai_center", True), ("field_masking", False),
            ("attachment_classification", True), ("webhook_events", True),
        ]:
            if code in existing_toggles:
                continue
            db.add(TenantFeatureToggle(
                id=generate_uuid(), tenant_id=TENANT_ID,
                feature_code=code, enabled=enabled,
            ))
            added["feature_toggles"] += 1

        # ---- 默认审批策略（预置一条可用的顺序审批；审批人/角色后续在「系统设置→审批策略」调整） ----
        from app.domains.admin.models import ApprovalPolicy
        existing_pol = {p.biz_type for p in (await db.execute(
            select(ApprovalPolicy).where(ApprovalPolicy.tenant_id == TENANT_ID)
        )).scalars().all()}
        for biz_type, pname in [("contract_version", "合同审批（默认）"), ("order", "订单审批（默认）"),
                                ("service_ticket", "售后工单审批（默认）")]:
            if biz_type in existing_pol:
                continue
            db.add(ApprovalPolicy(
                id=generate_uuid(), tenant_id=TENANT_ID,
                biz_type=biz_type, name=pname,
                approver_rules_json=[{"type": "role", "value": "admin"}],
                approval_mode="sequential", enabled=True, priority=0,
            ))
            added["approval_policies"] += 1

        # 跨所有租户增量下发标准角色权限:任何已拥有标准角色的租户,其标准角色
        # 都会自动补齐目录里的新权限(只增不删、不给缺角色的租户凭空建角色)。
        # 这样每次部署后,新功能权限自动到达所有环境的标准角色。
        from app.common.rbac_sync import sync_all_tenants_additive
        _rbac = await sync_all_tenants_additive(db)
        added["role_perms"] += _rbac.get("_total_perms_added", 0)

        await db.commit()

        print("Seed sync complete:")
        for k, v in added.items():
            print(f"  {k:16s} +{v}")
        if added["users"] == 1:
            print("  Admin: admin / admin123  (CHANGE THIS PASSWORD IMMEDIATELY)")


if __name__ == "__main__":
    # Default = include demo data (unchanged CI behavior: `python -m scripts.seed`).
    # Production installs pass --production / --no-demo to skip demo customers/projects.
    _include_demo = not ({"--production", "--no-demo"} & set(sys.argv[1:]))
    asyncio.run(seed(include_demo=_include_demo))
