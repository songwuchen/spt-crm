# -*- coding: utf-8 -*-
"""205: 创建「1.2.8生产卡/补充流程-电气车间」角色并挂李同民、张雨辰。"""
from __future__ import annotations

import json
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SUDO = f"echo {PWD} | sudo -S"
TENANT = "00000000-0000-0000-0000-000000000001"
OUT = r"G:\ruolin-a\spt-crm\_ensure_prod_elec_workshop_205_out.txt"

INNER = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
import app.domains.auth.models  # noqa: F401
import app.domains.organization.models  # noqa: F401
from sqlalchemy import select, text
from app.database import async_session_factory
from app.common.rbac_sync import ensure_prod_elec_workshop_role_members, ensure_business_roles
from app.domains.auth.models import Role, User, UserRole
from app.domains.auth.service import invalidate_tenant_auth_cache

async def main():
    tid = "%(tenant)s"
    async with async_session_factory() as db:
        created = await ensure_business_roles(db, tid, ["prod_elec_workshop"])
        res = await ensure_prod_elec_workshop_role_members(db, tid)
        await db.commit()
        await invalidate_tenant_auth_cache(tid)
        role = (await db.execute(
            select(Role).where(Role.tenant_id == tid, Role.code == "prod_elec_workshop")
        )).scalar_one_or_none()
        members = []
        if role:
            rows = (await db.execute(
                select(User.username, User.real_name).join(
                    UserRole, UserRole.user_id == User.id
                ).where(UserRole.tenant_id == tid, UserRole.role_id == role.id).order_by(User.real_name)
            )).all()
            members = [{"username": r[0], "real_name": r[1]} for r in rows]
            perms = (await db.execute(text("""
                SELECT DISTINCT p.code FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = :rid
                  AND p.code IN ('form_data:view','form_data:edit','approval:approve','approval:decide')
                ORDER BY p.code
            """), {"rid": role.id})).scalars().all()
        else:
            perms = []
        out = {
            "created_roles": created,
            "sync": res,
            "role": {"code": role.code, "name": role.name, "scope_by_resource": role.scope_by_resource} if role else None,
            "members": members,
            "key_perms": list(perms),
        }
        print("RESULT", json.dumps(out, ensure_ascii=False, default=str))

asyncio.run(main())
''' % {"tenant": TENANT}


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=25, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_ensure_prod_elec_workshop.py", "w") as f:
        f.write(INNER)

    def run(cmd: str) -> str:
        _i, o, e = c.exec_command(cmd, timeout=180)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        if err.strip():
            print("STDERR:", err)
        return out

    run(
        f"{SUDO} docker compose -f /home/swc/spt-crm/docker-compose.yml "
        "cp /tmp/_ensure_prod_elec_workshop.py backend:/tmp/_ensure_prod_elec_workshop.py"
    )
    out = run(
        f"{SUDO} docker compose -f /home/swc/spt-crm/docker-compose.yml exec -T backend "
        "sh -c 'cd /app && PYTHONPATH=/app python /tmp/_ensure_prod_elec_workshop.py'"
    )
    run(
        f"{SUDO} docker compose -f /home/swc/spt-crm/docker-compose.yml "
        "cp backend:/tmp/_ensure_prod_elec_workshop_out.json /tmp/_ensure_prod_elec_workshop_out.json 2>/dev/null || true"
    )
    Path = __import__("pathlib").Path
    Path(OUT).write_text(out, encoding="utf-8")
    c.close()
    print(out)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
