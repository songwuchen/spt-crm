#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 为张光所在角色开通收款登记全权限（含 form_data:delete）。"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import paramiko

OUT = Path(r"G:\ruolin-a\spt-crm\_grant_zhangguang_payment_205.txt")
HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
TARGET_NAME = "张光"
TENANT = "00000000-0000-0000-0000-000000000001"

# 收款登记模块所需权限（含删除）
NEED_PERMS = [
    "form_data:view", "form_data:create", "form_data:edit", "form_data:delete",
    "form:view", "form:manage",
    "workflow:view", "workflow:manage", "workflow:activate",
    "dashboard:view", "dashboard:manage",
    "payment:view", "payment:edit",
    "approval:view", "approval:approve", "approval:decide",
    "attachment:upload", "attachment:download",
]

REMOTE = rf'''
import asyncio, json, sys, uuid
sys.stdout.reconfigure(encoding="utf-8")
import app.domains.organization.models  # noqa: F401
from sqlalchemy import select, text
from app.common.rbac_catalog import CORE, LOWCODE_DESIGN
from app.database import async_session_factory, generate_uuid
from app.domains.auth.models import Role, User, UserRole, Permission, RolePermission
from app.domains.auth.service import get_user_permissions, invalidate_tenant_auth_cache, invalidate_user_auth_cache
from app.domains.lowcode import service as lc

TARGET = {TARGET_NAME!r}
TID = {TENANT!r}
NEED_PERMS = {json.dumps(NEED_PERMS, ensure_ascii=False)}

async def main():
    out = {{"target": TARGET, "steps": []}}
    async with async_session_factory() as db:
        u = (await db.execute(text("""
            SELECT id, username, real_name, is_active
            FROM users
            WHERE tenant_id = :tid AND real_name = :n
            LIMIT 1
        """), {{"tid": TID, "n": TARGET}})).mappings().first()
        if not u:
            out["error"] = "user not found"
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return
        user_id = u["id"]
        out["user"] = dict(u)

        roles = (await db.execute(
            select(Role).join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, UserRole.tenant_id == TID)
            .order_by(Role.code)
        )).scalars().all()
        out["roles_before"] = [
            {{"code": r.code, "name": r.name, "data_scope": r.data_scope,
              "scope_by_resource": r.scope_by_resource or {{}}}}
            for r in roles
        ]
        if not roles:
            out["error"] = "user has no roles"
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return

        # 优先改 finance / finance_manager；否则改第一个角色
        role = next((r for r in roles if r.code == "finance_manager"), None)
        if not role:
            role = next((r for r in roles if r.code == "finance"), None)
        if not role:
            role = roles[0]
        out["target_role"] = {{"id": role.id, "code": role.code, "name": role.name}}

        # 回款模块看全部（form 列表 payment_registration 走 role.data_scope）
        sbr = dict(role.scope_by_resource or {{}})
        changed_sbr = False
        if sbr.get("payment") != "all":
            sbr["payment"] = "all"
            role.scope_by_resource = sbr
            changed_sbr = True
        if changed_sbr:
            out["steps"].append(f"scope_by_resource updated: {{role.scope_by_resource}}")

        if role.data_scope != "all":
            role.data_scope = "all"
            out["steps"].append("data_scope set to all")

        perm_map = {{p.code: p.id for p in (await db.execute(select(Permission))).scalars().all()}}
        have = set((await db.execute(
            select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )).scalars().all())

        want = set(NEED_PERMS) | set(CORE) | set(LOWCODE_DESIGN)
        added = []
        for code in sorted(want - have):
            pid = perm_map.get(code)
            if not pid:
                out.setdefault("missing_perm_defs", []).append(code)
                continue
            db.add(RolePermission(
                id=generate_uuid(), tenant_id=TID, role_id=role.id, permission_id=pid,
            ))
            added.append(code)
        if added:
            out["steps"].append(f"added perms: {{added}}")
        else:
            out["steps"].append("all target perms already present")

        await lc.ensure_builtin_form(db, TID, "payment_registration", {{"sub": user_id}})
        out["steps"].append("payment_registration template ensured")

        await db.commit()

        await invalidate_user_auth_cache(user_id, TID)
        await invalidate_tenant_auth_cache(TID)
        perms = await get_user_permissions(db, user_id, TID)
        out["key_perms"] = {{k: (k in perms) for k in NEED_PERMS}}
        out["perm_count"] = len(perms)

        roles_after = (await db.execute(
            select(Role.code, Role.name, Role.data_scope, Role.scope_by_resource)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, UserRole.tenant_id == TID)
            .order_by(Role.code)
        )).all()
        out["roles_after"] = [
            {{"code": c, "name": n, "data_scope": ds, "scope_by_resource": sbr or {{}}}}
            for c, n, ds, sbr in roles_after
        ]

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    b64 = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
    inner = f"echo {b64} | base64 -d > /tmp/_grant_zg_payment.py && PYTHONPATH=/app python /tmp/_grant_zg_payment.py"
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
