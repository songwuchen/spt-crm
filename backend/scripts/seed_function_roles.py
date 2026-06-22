"""Idempotent seeding of FUNCTION-BASED roles (财务/设计/生产/售后/...) with
their permission sets and data_scope.

Review ROLE_DEFS below, then run INSIDE the backend container:

    # 1) dry-run — prints what would change, writes nothing
    docker compose exec -T backend python -m scripts.seed_function_roles
    # 2) apply
    docker compose exec -T backend python -m scripts.seed_function_roles --apply

Safe & idempotent: creates/updates roles by (tenant_id, code), syncs each role's
permissions to exactly the listed codes, and sets data_scope. Does NOT touch users
or existing person-named roles. Re-runnable.

TENANT_ID defaults to the demo/main tenant; override with env TENANT_ID.
"""
import asyncio
import os
import sys

from sqlalchemy import select

from app.database import async_session_factory, generate_uuid
from app.domains.auth.models import Role, Permission, RolePermission
import app.domains.organization.models  # noqa: F401 — register ORM mappers (User.user_departments)

TENANT_ID = os.environ.get("TENANT_ID", "00000000-0000-0000-0000-000000000001")
APPLY = "--apply" in sys.argv

# Permissions every business role gets.
CORE = [
    "notification:view",
    "attachment:download", "attachment:upload",
    "task:view", "task:create", "task:edit",
    "approval:view", "approval:resubmit", "approval:withdraw",
]

# scope: self / dept / all   (None == self)
ROLE_DEFS = [
    {
        "code": "sales_rep", "name": "销售专员", "scope": "self",
        "desc": "商机 owner：客户/线索/商机/报价；上下游只读",
        "perms": CORE + [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit", "lead:qualify", "lead:discard",
            "project:view", "project:create", "project:edit", "project:advance",
            "quote:view", "quote:create", "quote:edit",
            "solution:view", "contract:view", "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view", "dashboard:view",
        ],
    },
    {
        "code": "sales_manager", "name": "销售主管", "scope": "dept",
        "desc": "本部门子树销售数据 + 审批 + 提成查看",
        "perms": CORE + [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit", "lead:qualify", "lead:discard",
            "project:view", "project:create", "project:edit", "project:advance",
            "quote:view", "quote:create", "quote:edit",
            "solution:view", "contract:view", "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view", "commission:view", "dashboard:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "sales_director", "name": "销售总监", "scope": "all",
        "desc": "全租户销售数据 + 审批",
        "perms": CORE + [
            "customer:view", "customer:create", "customer:edit",
            "contact:view", "contact:create", "contact:edit",
            "lead:view", "lead:create", "lead:edit", "lead:qualify", "lead:discard",
            "project:view", "project:create", "project:edit", "project:advance",
            "quote:view", "quote:create", "quote:edit",
            "solution:view", "contract:view", "delivery:view", "payment:view",
            "order:view", "product:view", "tender:view", "commission:view", "dashboard:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "biz_support", "name": "商务/标书专员", "scope": "dept",
        "desc": "市场支持/国际业务支持：标书 + 协助报价",
        "perms": CORE + [
            "customer:view", "project:view", "quote:view", "quote:edit",
            "contract:view", "product:view",
            "tender:view", "tender:create", "tender:edit", "tender:delete",
        ],
    },
    {
        "code": "design_engineer", "name": "方案设计工程师", "scope": "self",
        "desc": "研究院/技术/工艺：方案 + 技术变更；靠 assignee 看到被指派的商机",
        "perms": CORE + [
            "customer:view", "project:view", "quote:view", "contract:view", "product:view",
            "solution:view", "solution:create", "solution:edit",
            "change:view", "change:create", "change:edit",
        ],
    },
    {
        "code": "tech_chief", "name": "技术总工/评审", "scope": "all",
        "desc": "全局技术只读 + 方案/变更评审与审批",
        "perms": CORE + [
            "customer:view", "project:view", "quote:view", "contract:view", "product:view",
            "solution:view", "solution:create", "solution:edit",
            "change:view", "change:create", "change:edit",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "production", "name": "生产/交付专员", "scope": "dept",
        "desc": "生产管理部及车间：交付里程碑 + 订单",
        "perms": CORE + [
            "customer:view", "project:view", "contract:view", "product:view",
            "delivery:view", "delivery:edit",
            "order:view", "order:create", "order:edit",
        ],
    },
    {
        "code": "production_manager", "name": "生产主管", "scope": "dept",
        "desc": "生产负责人：交付/订单全权 + 交付审批",
        "perms": CORE + [
            "customer:view", "project:view", "contract:view", "product:view", "quote:view",
            "delivery:view", "delivery:edit", "delivery:delete",
            "order:view", "order:create", "order:edit", "order:delete",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "finance", "name": "财务专员", "scope": "all",
        "desc": "全公司回款/清欠/发票/提成/保函；合同等只读",
        "perms": CORE + [
            "customer:view", "project:view", "quote:view", "contract:view", "order:view",
            "payment:view", "payment:edit",
            "collection:view", "collection:edit", "collection:manage",
            "commission:view", "commission:edit",
            "guarantee:view", "guarantee:edit",
        ],
    },
    {
        "code": "finance_manager", "name": "财务主管", "scope": "all",
        "desc": "财务负责人：+ 合同财务条款 + 金额/毛利红线审批",
        "perms": CORE + [
            "customer:view", "project:view", "quote:view", "order:view",
            "contract:view", "contract:edit",
            "payment:view", "payment:edit",
            "collection:view", "collection:edit", "collection:manage",
            "commission:view", "commission:edit", "commission:manage",
            "guarantee:view", "guarantee:edit",
            "approval:approve", "approval:decide", "approval:delegate", "approval:manage",
        ],
    },
    {
        "code": "collection_officer", "name": "清欠专员", "scope": "all",
        "desc": "清欠办：应收清欠 + 回款登记",
        "perms": CORE + [
            "customer:view", "contract:view",
            "collection:view", "collection:edit", "collection:manage",
            "payment:view", "payment:edit",
        ],
    },
    {
        "code": "service_engineer", "name": "售后工程师", "scope": "self",
        "desc": "客户服务部：工单 + 实测 + 设备档案",
        "perms": CORE + [
            "customer:view", "contract:view", "product:view",
            "service:view", "service:create", "service:edit",
        ],
    },
    {
        "code": "service_manager", "name": "售后主管", "scope": "dept",
        "desc": "售后负责人：工单全权 + 审批",
        "perms": CORE + [
            "customer:view", "contract:view", "product:view",
            "service:view", "service:create", "service:edit", "service:delete",
            "approval:approve", "approval:decide",
        ],
    },
    {
        "code": "procurement", "name": "采购专员", "scope": "dept",
        "desc": "采购部/外购：订单 + 产品；合同/交付只读",
        "perms": CORE + [
            "project:view", "contract:view", "delivery:view",
            "order:view", "order:create", "order:edit",
            "product:view", "product:edit",
        ],
    },
    {
        "code": "legal", "name": "合同法务", "scope": "all",
        "desc": "法务管理小组：合同审查/签署 + 合同审批",
        "perms": CORE + [
            "customer:view", "project:view", "quote:view",
            "contract:view", "contract:edit", "contract:sign",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
    {
        "code": "executive", "name": "高管(只读)", "scope": "all",
        "desc": "总经办/总经理：全模块只读 + 审批 + 审计；不可增改",
        "perms": CORE + [
            "customer:view", "contact:view", "lead:view", "project:view", "quote:view",
            "contract:view", "solution:view", "change:view", "delivery:view",
            "payment:view", "collection:view", "commission:view", "guarantee:view",
            "order:view", "tender:view", "product:view", "service:view", "audit:view",
            "dashboard:view",
            "approval:approve", "approval:decide", "approval:delegate",
        ],
    },
]


async def main():
    async with async_session_factory() as db:
        perms = (await db.execute(select(Permission))).scalars().all()
        pid = {p.code: p.id for p in perms}

        print(f"tenant={TENANT_ID}  mode={'APPLY' if APPLY else 'DRY-RUN (use --apply to write)'}\n")
        for rd in ROLE_DEFS:
            codes = list(dict.fromkeys(rd["perms"]))  # dedupe, keep order
            missing = [c for c in codes if c not in pid]
            if missing:
                print(f"  !! {rd['code']}: unknown permission codes -> {missing}")
            want = {pid[c] for c in codes if c in pid}

            role = (await db.execute(
                select(Role).where(Role.tenant_id == TENANT_ID, Role.code == rd["code"])
            )).scalar_one_or_none()
            if role is None:
                action = "CREATE"
                if APPLY:
                    role = Role(
                        id=generate_uuid(), tenant_id=TENANT_ID, code=rd["code"],
                        name=rd["name"], description=rd.get("desc"),
                        data_scope=rd["scope"], is_system=False,
                    )
                    db.add(role)
                    await db.flush()
            else:
                action = "UPDATE"
                if APPLY:
                    role.name = rd["name"]
                    role.description = rd.get("desc")
                    role.data_scope = rd["scope"]

            added = removed = 0
            if APPLY and role is not None:
                existing = (await db.execute(
                    select(RolePermission).where(RolePermission.role_id == role.id)
                )).scalars().all()
                have = {rp.permission_id for rp in existing}
                for rp in existing:
                    if rp.permission_id not in want:
                        await db.delete(rp); removed += 1
                for p_id in (want - have):
                    db.add(RolePermission(
                        id=generate_uuid(), tenant_id=TENANT_ID,
                        role_id=role.id, permission_id=p_id,
                    )); added += 1

            print(f"  {action:6} {rd['code']:20} scope={rd['scope']:4} perms={len(want):2}"
                  + (f"  (+{added}/-{removed})" if APPLY else ""))

        if APPLY:
            await db.commit()
            print("\n✓ committed.")
        else:
            print("\n(dry-run) nothing written. Re-run with --apply to create the roles.")


if __name__ == "__main__":
    asyncio.run(main())
