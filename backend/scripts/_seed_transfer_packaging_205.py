# -*- coding: utf-8 -*-
"""205: 角色「转新乡、工艺包装」挂成员（成员维护在用户管理 → 角色）。"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.common.rbac_sync import ensure_transfer_packaging_role_members
from app.database import async_session_maker
from app.domains.auth.models import Role, User, UserRole

TID = "00000000-0000-0000-0000-000000000001"


async def main() -> None:
    async with async_session_maker() as db:
        info = await ensure_transfer_packaging_role_members(db, TID)
        await db.commit()
        print("ensure_transfer_packaging_role_members:", info)

        role = (
            await db.execute(
                select(Role).where(Role.tenant_id == TID, Role.code == "transfer_packaging")
            )
        ).scalar_one_or_none()
        if not role:
            print("ERROR: role transfer_packaging missing")
            return

        rows = (
            await db.execute(
                select(User.real_name, User.username)
                .join(UserRole, UserRole.user_id == User.id)
                .where(UserRole.tenant_id == TID, UserRole.role_id == role.id)
                .order_by(User.real_name)
            )
        ).all()
        print("role transfer_packaging members:", len(rows))
        for name, uname in rows:
            print(f"  - {name} ({uname})")


if __name__ == "__main__":
    asyncio.run(main())
