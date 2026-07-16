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
    # Per-row upsert. Safe to re-run on every deploy: missing permissions, roles,
    # demo customers / projects / stages / feature toggles are added; existing rows
    # are left alone (so operator edits — passwords, customized stage gates,
    # toggle states, real customer data sharing a demo name — are not clobbered).
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
            ("lead:review", "审核线索", "线索"),
            ("project:view", "查看商机", "商机"),
            ("project:create", "创建商机", "商机"),
            ("project:edit", "编辑商机", "商机"),
            ("project:delete", "删除商机", "商机"),
            ("project:advance", "推进商机阶段", "商机"),
            ("project:transfer", "转移商机负责人", "商机"),
            ("quote:view", "查看报价", "报价"),
            ("quote:create", "创建报价", "报价"),
            ("quote:edit", "编辑报价", "报价"),
            ("quote:delete", "删除报价", "报价"),
            ("quote:view_cost", "查看报价成本/毛利", "报价"),
            ("quote:view_discount", "查看报价折扣", "报价"),
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
            ("task:view", "查看任务", "任务"),
            ("task:create", "创建任务", "任务"),
            ("task:edit", "编辑任务", "任务"),
            ("task:delete", "删除任务", "任务"),
            ("notification:view", "查看通知", "通知"),
            ("notification:manage", "管理通知", "通知"),
            ("product:view", "查看产品", "产品"),
            ("product:create", "创建产品", "产品"),
            ("product:edit", "编辑产品", "产品"),
            ("product:delete", "删除产品", "产品"),
            ("order:view", "查看订单", "订单"),
            ("order:create", "创建订单", "订单"),
            ("order:edit", "编辑订单", "订单"),
            ("order:delete", "删除订单", "订单"),
            ("tender:view", "查看标书", "标书"),
            ("tender:create", "创建标书", "标书"),
            ("tender:edit", "编辑标书", "标书"),
            ("tender:delete", "删除标书", "标书"),
            ("commission:view", "查看提成", "提成"),
            ("commission:edit", "编辑提成", "提成"),
            ("commission:manage", "管理提成政策", "提成"),
            ("collection:view", "查看应收清欠", "应收清欠"),
            ("collection:edit", "编辑应收清欠", "应收清欠"),
            ("collection:manage", "管理应收清欠", "应收清欠"),
            ("guarantee:view", "查看保函", "保函"),
            ("guarantee:edit", "编辑保函", "保函"),
            ("audit:view", "查看审计", "审计"),
            ("dashboard:view", "查看销售目标/仪表盘", "报表"),
            ("role:view", "查看角色", "系统"),
            ("role:edit", "编辑角色", "系统"),
            ("role:manage", "管理角色", "系统"),
            ("user:view", "查看用户", "系统"),
            ("user:manage", "管理用户", "系统"),
            ("dept:view", "查看部门", "组织"),
            ("dept:manage", "管理部门", "组织"),
            ("tenant:view", "查看租户", "平台"),
            ("tenant:manage", "管理租户", "平台"),
            # ---- 扩展平台(低代码): 表单引擎 / 流程引擎 / 仪表盘 ----
            ("form:view", "查看表单模板", "扩展平台"),
            ("form:manage", "设计/管理表单模板", "扩展平台"),
            ("form_data:view", "查看表单数据", "扩展平台"),
            ("form_data:create", "填报表单数据", "扩展平台"),
            ("form_data:edit", "编辑表单数据", "扩展平台"),
            ("form_data:delete", "删除表单数据", "扩展平台"),
            ("workflow:view", "查看流程定义", "扩展平台"),
            ("workflow:manage", "设计/管理流程定义", "扩展平台"),
            ("dashboard:manage", "设计/管理仪表盘", "扩展平台"),
        ]
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
        ]
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

        await db.commit()

        print("Seed sync complete:")
        for k, v in added.items():
            print(f"  {k:16s} +{v}")
        if added["users"] == 1:
            print("  Admin: admin / admin123  (CHANGE THIS PASSWORD IMMEDIATELY)")


if __name__ == "__main__":
    asyncio.run(seed())
