"""安装「部门编号基础表」并从简道云 dump 按部门名灌入编号。

Idempotent：表内已有任意记录则跳过（ensure 路径亦同）。

Run:
  python -m scripts.seed_department_codes
  python -m scripts.seed_department_codes <tenant_id>
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.database import async_session_factory
from app.domains.lowcode import service as lc_svc
from app.domains.lowcode.dept_code import seed_department_codes_if_empty


async def _pick_user_id(db, tenant_id: str) -> str:
    for sql in (
        "SELECT id FROM users WHERE tenant_id = :t AND COALESCE(is_deleted, false) = false "
        "ORDER BY created_at ASC NULLS LAST LIMIT 1",
        "SELECT id FROM users WHERE tenant_id = :t ORDER BY created_at ASC NULLS LAST LIMIT 1",
        "SELECT id FROM users WHERE tenant_id = :t LIMIT 1",
    ):
        try:
            row = (await db.execute(text(sql), {"t": tenant_id})).first()
            if row and row[0]:
                return str(row[0])
        except Exception:
            await db.rollback()
    return "00000000-0000-0000-0000-000000000000"


async def seed_tenant(db, tenant_id: str) -> int:
    user_id = await _pick_user_id(db, tenant_id)
    user = {"sub": user_id, "real_name": "system", "username": "system", "roles": []}
    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, "department_code_base", user)
    # ensure 内已尝试灌入；若因历史空表未灌，再强制一次（仅空表有效）
    n = await seed_department_codes_if_empty(db, tenant_id, tpl.id, user)
    await db.commit()
    print(f"[{tenant_id[:8]}] department_code_base tpl={tpl.id} seeded={n}")
    return n


async def main() -> None:
    tenant_arg = sys.argv[1] if len(sys.argv) > 1 else None
    async with async_session_factory() as db:
        if tenant_arg:
            tenant_ids = [tenant_arg]
        else:
            rows = (await db.execute(text(
                "SELECT id FROM platform_tenants UNION SELECT DISTINCT tenant_id FROM users"
            ))).all()
            tenant_ids = [str(r[0]) for r in rows if r[0]]
            if not tenant_ids:
                tenant_ids = ["00000000-0000-0000-0000-000000000001"]
        for tid in tenant_ids:
            await seed_tenant(db, tid)
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
