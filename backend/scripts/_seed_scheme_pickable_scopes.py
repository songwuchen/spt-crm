# -*- coding: utf-8 -*-
"""按简道云方案/图纸「设计指派」「科室」完善可选范围成员。

设计指派(JDY role 63815e3a…) 流程侧具名：周彦立、李兴玉、樊磊、刘松潮、吕芹
科室(JDY limit.depart)：中央研究院、研发中心*研发试验组
CRM 组织树里设计一室/二室/筛板组未挂在研究院下，一并纳入科室可选。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database import generate_uuid
from app.domains.organization.models import Department
from app.domains.organization.pickable_scope_models import PickableScope
from app.domains.organization.pickable_scope_service import ensure_preset_scopes
from app.domains.auth.models import User

# 简道云流程条件里写明的设计指派人选
ROOM_LEADER_NAMES = ["周彦立", "李兴玉", "樊磊", "刘松潮", "吕芹"]

# 简道云科室 limit + CRM 实际各室（路径未挂研究院下）
OFFICE_DEPT_NAMES = [
    "中央研究院",
    "研发中心*研发试验组",
    "设计一室",
    "设计二室",
    "筛板组",
]


def load_db_url() -> str:
    for p in (Path(".env"), Path("../.env")):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no DATABASE_URL")


async def upsert_scope(
    db: AsyncSession, tenant_id: str, *,
    code: str, name: str, kind: str, description: str, rules: dict,
) -> PickableScope:
    row = (
        await db.execute(
            select(PickableScope).where(
                PickableScope.tenant_id == tenant_id, PickableScope.code == code,
            )
        )
    ).scalar_one_or_none()
    if row:
        row.name = name
        row.description = description
        row.kind = kind
        row.rules = dict(rules)
        row.is_system = True
        return row
    row = PickableScope(
        id=generate_uuid(),
        tenant_id=tenant_id,
        code=code,
        name=name,
        kind=kind,
        description=description,
        is_system=True,
        rules=dict(rules),
    )
    db.add(row)
    return row


async def main() -> None:
    eng = create_async_engine(load_db_url())
    Session = sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        tenants = (
            await db.execute(text("SELECT DISTINCT tenant_id FROM users LIMIT 20"))
        ).scalars().all()
        if not tenants:
            # fallback pickable_scopes / departments
            tenants = (
                await db.execute(text("SELECT DISTINCT tenant_id FROM departments LIMIT 20"))
            ).scalars().all()
        print("tenants", tenants)

        for tid in tenants:
            await ensure_preset_scopes(db, tid)

            users = list(
                (
                    await db.execute(
                        select(User).where(
                            User.tenant_id == tid,
                            User.real_name.in_(ROOM_LEADER_NAMES),
                            User.is_active == True,  # noqa: E712
                        )
                    )
                ).scalars().all()
            )
            by_name = {u.real_name: u for u in users}
            missing = [n for n in ROOM_LEADER_NAMES if n not in by_name]
            user_ids = [by_name[n].id for n in ROOM_LEADER_NAMES if n in by_name]
            print(f"[{tid}] room leaders found={len(user_ids)} missing={missing}")
            for n in ROOM_LEADER_NAMES:
                u = by_name.get(n)
                if u:
                    print(f"  - {n} ({u.username})")

            depts = list(
                (
                    await db.execute(
                        select(Department).where(
                            Department.tenant_id == tid,
                            Department.name.in_(OFFICE_DEPT_NAMES),
                        )
                    )
                ).scalars().all()
            )
            dept_by_name = {d.name: d for d in depts}
            missing_d = [n for n in OFFICE_DEPT_NAMES if n not in dept_by_name]
            dept_ids = [dept_by_name[n].id for n in OFFICE_DEPT_NAMES if n in dept_by_name]
            print(f"[{tid}] offices found={len(dept_ids)} missing={missing_d}")
            for n in OFFICE_DEPT_NAMES:
                d = dept_by_name.get(n)
                if d:
                    print(f"  - {n}")

            await upsert_scope(
                db, tid,
                code="room_leaders",
                name="方案管理-设计指派",
                kind="person",
                description="方案管理「设计指派」人选范围；在此直接勾选成员。",
                rules={
                    "role_codes": [],
                    "user_ids": user_ids,
                    "dept_ids": [],
                    "include_children": True,
                },
            )
            await upsert_scope(
                db, tid,
                code="scheme_offices",
                name="方案管理-科室",
                kind="department",
                description="方案管理「科室」可选部门范围。",
                rules={
                    "role_codes": [],
                    "user_ids": [],
                    "dept_ids": dept_ids,
                    "include_children": True,
                },
            )
            await db.commit()
            print(f"[{tid}] scopes updated")

    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
