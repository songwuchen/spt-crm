#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 13701371773 开通报价管理查看成本价（quote_cost_viewer 角色）。"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import paramiko

PHONE = "13701371773"
HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
TENANT = "00000000-0000-0000-0000-000000000001"
OUT = Path(r"G:\ruolin-a\spt-crm\_grant_quote_cost_13701371773_205.txt")

ROLE_CODE = "quote_cost_viewer"
ROLE_NAME = "报价成本价查看"
ROLE_DESC = "报价管理：可查看成本价与成本价附件（只读）"
ROLE_PERMS = [
    "form_data:view",
    "form:view",
    "workflow:view",
    "approval:view",
    "attachment:download",
    "quote:view_cost",
]

REMOTE = rf'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
import app.domains.organization.models  # noqa: F401
from sqlalchemy import select, text
from app.database import async_session_factory, generate_uuid
from app.domains.auth.models import Role, Permission, RolePermission, UserRole
from app.domains.auth.service import get_user_permissions, invalidate_tenant_auth_cache, invalidate_user_auth_cache
from app.domains.lowcode.field_permission import filter_read
from app.domains.lowcode.quote_management_fields import prepare_quote_field_defs, QUOTE_COST_VISIBLE_ROLES

PHONE = {PHONE!r}
TID = {TENANT!r}
ROLE_CODE = {ROLE_CODE!r}
ROLE_NAME = {ROLE_NAME!r}
ROLE_DESC = {ROLE_DESC!r}
ROLE_PERMS = {json.dumps(ROLE_PERMS, ensure_ascii=False)}

async def main():
    out = {{"phone": PHONE, "quote_cost_visible_roles": QUOTE_COST_VISIBLE_ROLES, "steps": []}}
    async with async_session_factory() as db:
        u = (await db.execute(text("""
            SELECT id, username, real_name, phone, is_active FROM users
            WHERE tenant_id=:t AND phone=:p LIMIT 1
        """), {{"t": TID, "p": PHONE}})).mappings().first()
        if not u:
            out["error"] = "user not found"
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return
        uid = u["id"]
        out["user"] = dict(u)

        if ROLE_CODE not in QUOTE_COST_VISIBLE_ROLES:
            out["warn"] = f"{{ROLE_CODE}} not in QUOTE_COST_VISIBLE_ROLES yet — deploy backend first"

        role = (await db.execute(
            select(Role).where(Role.tenant_id == TID, Role.code == ROLE_CODE)
        )).scalar_one_or_none()
        if not role:
            role = Role(
                id=generate_uuid(),
                tenant_id=TID,
                code=ROLE_CODE,
                name=ROLE_NAME,
                description=ROLE_DESC,
                data_scope="all",
                scope_by_resource={{}},
                is_system=False,
            )
            db.add(role)
            await db.flush()
            out["steps"].append("created role " + ROLE_CODE)
        else:
            role.name = ROLE_NAME
            role.description = ROLE_DESC
            role.data_scope = "all"
            out["steps"].append("updated role " + ROLE_CODE)

        perm_map = {{p.code: p.id for p in (await db.execute(select(Permission))).scalars().all()}}
        have = set((await db.execute(
            select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )).scalars().all())
        added = []
        for code in sorted(set(ROLE_PERMS) - have):
            pid = perm_map.get(code)
            if not pid:
                out.setdefault("missing_perm_defs", []).append(code)
                continue
            db.add(RolePermission(
                id=generate_uuid(), tenant_id=TID, role_id=role.id, permission_id=pid,
            ))
            added.append(code)
        if added:
            out["steps"].append("added perms: " + str(added))

        link = (await db.execute(
            select(UserRole).where(
                UserRole.tenant_id == TID, UserRole.user_id == uid, UserRole.role_id == role.id,
            )
        )).scalar_one_or_none()
        if not link:
            db.add(UserRole(id=generate_uuid(), tenant_id=TID, user_id=uid, role_id=role.id))
            out["steps"].append("assigned role to user")
        else:
            out["steps"].append("user already has role")

        await db.commit()
        await invalidate_user_auth_cache(uid, TID)
        await invalidate_tenant_auth_cache(TID)

        roles = list((await db.execute(
            select(Role.code).join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == uid, UserRole.tenant_id == TID)
        )).scalars().all())
        out["roles_after"] = roles
        perms = await get_user_permissions(db, uid, TID)
        out["quote_view_cost_perm"] = "quote:view_cost" in perms

        sample_defs = prepare_quote_field_defs([
            {{"id": "cost_price", "type": "number", "label": "成本价"}},
            {{"id": "cost_attachments", "type": "file", "label": "成本价附件"}},
        ])
        sample_data = {{"cost_price": 12345.6, "cost_attachments": [{{"id": "a1", "name": "c.xlsx"}}]}}
        _, filtered = filter_read(sample_defs, sample_data, roles)
        out["cost_price_visible"] = "cost_price" in filtered
        out["cost_attachments_visible"] = "cost_attachments" in filtered

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    b64 = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
    inner = f"echo {b64} | base64 -d > /tmp/_grant_quote_cost.py && PYTHONPATH=/app python /tmp/_grant_quote_cost.py"
    cmd = f"echo {PWD} | sudo -S docker exec -i spt-crm-backend-1 sh -c {json.dumps(inner)}"
    _, o, e = c.exec_command(cmd, timeout=180)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    text = out + (("\nSTDERR:\n" + err) if err.strip() else "") + f"\nexit={code}\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    c.close()
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
