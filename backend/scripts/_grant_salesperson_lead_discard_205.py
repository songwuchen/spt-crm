#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205：给 salesperson 角色补上 lead:discard，并清权限缓存。"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
OUT = Path(__file__).resolve().parents[2] / "_grant_salesperson_lead_discard_205.txt"

REMOTE = r'''
# -*- coding: utf-8 -*-
import asyncio
from sqlalchemy import text
from app.database import async_session_factory, generate_uuid
from app.domains.auth.service import invalidate_tenant_auth_cache

ROLE_CODE = "salesperson"
PERM = "lead:discard"
TID = "00000000-0000-0000-0000-000000000001"
WANGJING = "7bda9e1c-d067-403f-a850-bfc2d93595af"

async def main():
    async with async_session_factory() as db:
        role = (await db.execute(text("""
            SELECT id::text AS id, code, name FROM roles
            WHERE tenant_id = :tid AND code = :code
        """), {"tid": TID, "code": ROLE_CODE})).mappings().first()
        print("ROLE", dict(role) if role else None)
        if not role:
            return

        perm = (await db.execute(text("""
            SELECT id::text AS id, code FROM permissions WHERE code = :c
        """), {"c": PERM})).mappings().first()
        print("PERM", dict(perm) if perm else None)
        if not perm:
            return

        exists = (await db.execute(text("""
            SELECT 1 FROM role_permissions
            WHERE role_id = :rid AND permission_id = :pid AND tenant_id = :tid
        """), {"rid": role["id"], "pid": perm["id"], "tid": TID})).first()
        if exists:
            print("ALREADY_HAS", PERM)
        else:
            await db.execute(text("""
                INSERT INTO role_permissions
                  (id, tenant_id, role_id, permission_id, created_at, updated_at)
                VALUES (:id, :tid, :rid, :pid, NOW(), NOW())
            """), {
                "id": generate_uuid(), "tid": TID,
                "rid": role["id"], "pid": perm["id"],
            })
            await db.commit()
            print("GRANTED", PERM)

        await invalidate_tenant_auth_cache(TID)
        print("TENANT_CACHE_CLEARED")

        wj = (await db.execute(text("""
            SELECT DISTINCT p.code FROM permissions p
            JOIN role_permissions rp ON rp.permission_id = p.id
            JOIN user_roles ur ON ur.role_id = rp.role_id
            WHERE ur.user_id = :uid AND ur.tenant_id = :tid
              AND p.code LIKE 'lead:%'
            ORDER BY 1
        """), {"uid": WANGJING, "tid": TID})).scalars().all()
        print("WANGJING_LEAD_PERMS", list(wj))

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    b64 = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
    _, o, e = c.exec_command(
        f"echo {PWD} | sudo -S bash -lc "
        f"\"echo {b64} | base64 -d > /tmp/_grant_sp_discard.py && "
        f"cat /tmp/_grant_sp_discard.py | docker exec -i spt-crm-backend-1 python -\"",
        timeout=120,
    )
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    text = out + ("\nSTDERR:\n" + err if err.strip() else "")
    OUT.write_text(text, encoding="utf-8")
    print(text)
    c.close()


if __name__ == "__main__":
    main()
