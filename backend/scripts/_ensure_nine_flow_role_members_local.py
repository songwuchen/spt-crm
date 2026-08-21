# -*- coding: utf-8 -*-
"""本地：按简道云成员名单创建缺失账号，并挂到九流程业务角色。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import bcrypt

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
MEMBERS_JSON = ROOT / "docs" / "product" / "_jdy_nine_flow_role_members.json"
TENANT = "00000000-0000-0000-0000-000000000001"
DEFAULT_PWD = "Ruolin@2025"


async def ensure_user(db, tenant_id: str, username: str, real_name: str) -> tuple[object, bool]:
    from app.database import generate_uuid
    from app.domains.auth.models import User

    from sqlalchemy import select

    u = (
        await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == username)
        )
    ).scalar_one_or_none()
    if u:
        # 补姓名
        if real_name and (not u.real_name or u.real_name.startswith("产线") or u.real_name.startswith("单机")):
            if real_name and u.real_name != real_name and not real_name.endswith("物料编码"):
                u.real_name = real_name
        return u, False

    # 再按姓名找
    if real_name:
        by_name = (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.real_name == real_name,
                    User.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        if len(by_name) == 1:
            return by_name[0], False

    pwd = bcrypt.hashpw(DEFAULT_PWD.encode(), bcrypt.gensalt()).decode()
    u = User(
        id=generate_uuid(),
        tenant_id=tenant_id,
        username=username,
        real_name=real_name or username,
        password_hash=pwd,
        is_active=True,
        must_change_password=True,
    )
    db.add(u)
    await db.flush()
    return u, True


async def bind_role(db, tenant_id: str, role_code: str, user_ids: list[str]) -> int:
    from app.database import generate_uuid
    from app.domains.auth.models import Role, UserRole
    from sqlalchemy import select

    role = (
        await db.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == role_code)
        )
    ).scalar_one_or_none()
    if not role or not user_ids:
        return 0
    existing = set(
        (
            await db.execute(
                select(UserRole.user_id).where(
                    UserRole.tenant_id == tenant_id,
                    UserRole.role_id == role.id,
                    UserRole.user_id.in_(user_ids),
                )
            )
        ).scalars().all()
    )
    added = 0
    for uid in user_ids:
        if uid in existing:
            continue
        db.add(UserRole(
            id=generate_uuid(),
            tenant_id=tenant_id,
            user_id=uid,
            role_id=role.id,
        ))
        added += 1
    return added


async def main() -> None:
    import app.domains.organization.models  # noqa: F401 — UserDepartment etc.
    import app.domains.auth.models  # noqa: F401
    from app.common.rbac_sync import ensure_business_roles
    from app.database import async_session_factory

    if not MEMBERS_JSON.exists():
        raise SystemExit(f"missing {MEMBERS_JSON}")
    payload = json.loads(MEMBERS_JSON.read_text(encoding="utf-8"))
    roles = payload.get("roles") or {}

    async with async_session_factory() as db:
        created_roles = await ensure_business_roles(db, TENANT)
        print("created_roles", created_roles)

        summary = {}
        for code, info in roles.items():
            members = info.get("members") or []
            created_users = []
            bound_ids = []
            missing = []
            for m in members:
                uname = str(m.get("username") or "").strip()
                name = str(m.get("name") or "").strip()
                if not uname:
                    missing.append(m)
                    continue
                user, created = await ensure_user(db, TENANT, uname, name)
                if created:
                    created_users.append(f"{name}({uname})")
                bound_ids.append(user.id)
            added = await bind_role(db, TENANT, code, bound_ids)
            summary[code] = {
                "members_wanted": len(members),
                "users_created": created_users,
                "role_binds_added": added,
                "bound": len(bound_ids),
            }
            print(
                f"{code}: wanted={len(members)} created_users={len(created_users)} "
                f"binds+={added} bound={len(bound_ids)}"
            )
            for x in created_users:
                print(f"  +user {x}")

        await db.commit()

        # 打印最终成员
        from sqlalchemy import text
        print("\n=== final members ===")
        for code in roles:
            rows = (
                await db.execute(text("""
                    select u.real_name, u.username
                    from user_roles ur
                    join roles r on r.id = ur.role_id
                    join users u on u.id = ur.user_id
                    where r.tenant_id = :t and r.code = :c
                    order by u.real_name
                """), {"t": TENANT, "c": code})
            ).all()
            print(f"{code} ({len(rows)})")
            for n, u in rows:
                print(f"  {n}\t{u}")

        print("\nSUMMARY", json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
