# -*- coding: utf-8 -*-
"""本地：创建/更新 legal 角色并挂成员（杜习慧、孔雪、张孟杰）。"""
from __future__ import annotations

import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import text

import app.domains.auth.models  # noqa: F401
import app.domains.organization.models  # noqa: F401
from app.common.rbac_sync import ensure_legal_role_members
from app.database import async_session_factory

TENANT = "00000000-0000-0000-0000-000000000001"


async def main() -> None:
    async with async_session_factory() as db:
        dbname = (await db.execute(text("SELECT current_database()"))).scalar()
        result = await ensure_legal_role_members(db, TENANT)
        await db.commit()
        print("database:", dbname)
        print("ensure_legal_role_members:", json.dumps(result, ensure_ascii=False, default=str))

        row = (
            await db.execute(
                text(
                    "SELECT r.code, r.name, count(ur.user_id) AS n, "
                    "coalesce(string_agg(u.real_name, ',' ORDER BY u.real_name), '') AS members "
                    "FROM roles r "
                    "LEFT JOIN user_roles ur ON ur.role_id = r.id AND ur.tenant_id = r.tenant_id "
                    "LEFT JOIN users u ON u.id = ur.user_id "
                    "WHERE r.tenant_id = :t AND r.code = 'legal' "
                    "GROUP BY r.code, r.name"
                ),
                {"t": TENANT},
            )
        ).mappings().first()
        print("AFTER:", json.dumps(dict(row or {}), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
