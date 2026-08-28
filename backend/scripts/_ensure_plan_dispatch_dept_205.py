# -*- coding: utf-8 -*-
"""205: 计划调度室全员开通合同管理、生产卡/补充流程查看全部数据权限。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SUDO = f"echo {PWD} | sudo -S"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_ensure_plan_dispatch_dept_205_out.txt"
TENANT = "00000000-0000-0000-0000-000000000001"

PATCH_FILES = [
    "backend/app/common/rbac_catalog.py",
    "backend/app/common/rbac_sync.py",
]

INNER = '''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
import app.domains.auth.models  # noqa: F401
import app.domains.organization.models  # noqa: F401
from sqlalchemy import select, text
from app.database import async_session_factory
from app.common.rbac_sync import ensure_plan_dispatch_dept_role
from app.domains.auth.models import Role, User, UserRole
from app.domains.auth.service import invalidate_tenant_auth_cache

async def main():
    tid = "%(tenant)s"
    async with async_session_factory() as db:
        res = await ensure_plan_dispatch_dept_role(db, tid)
        await db.commit()
        await invalidate_tenant_auth_cache(tid)
        role = (await db.execute(
            select(Role).where(Role.tenant_id == tid, Role.code == "plan_dispatch_dept")
        )).scalar_one_or_none()
        members = []
        perms = []
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
                  AND p.code IN ('form_data:view','contract:view','order:view','product:view')
                ORDER BY p.code
            """), {"rid": role.id})).scalars().all()
        out = {
            "setup": res,
            "role": {
                "code": role.code,
                "name": role.name,
                "scope_by_resource": role.scope_by_resource,
            } if role else None,
            "members": members,
            "key_perms": list(perms),
        }
        print("RESULT", json.dumps(out, ensure_ascii=False, default=str))

asyncio.run(main())
''' % {"tenant": TENANT}


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    log: list[str] = []

    def run(cmd: str, timeout: int = 240) -> tuple[int, str]:
        print(">>", cmd.replace(PWD, "***")[:220], flush=True)
        _i, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        code = o.channel.recv_exit_status()
        text = out + (("\nSTDERR:\n" + err) if err.strip() else "")
        print(text[-4000:] if len(text) > 4000 else text, flush=True)
        log.append(text)
        return code, text

    compose = f"{SUDO} docker compose -f /home/swc/spt-crm/docker-compose.yml"
    for rel in PATCH_FILES:
        local = ROOT / rel
        remote_tmp = f"/tmp/{Path(rel).name}"
        sftp.put(str(local), remote_tmp)
        run(f"{compose} cp {remote_tmp} backend:/app/{rel.replace('backend/', '')}")

    with sftp.file("/tmp/_ensure_plan_dispatch_dept_run.py", "w") as f:
        f.write(INNER)
    sftp.close()

    run(f"{compose} cp /tmp/_ensure_plan_dispatch_dept_run.py backend:/tmp/_ensure_plan_dispatch_dept_run.py")
    code, out = run(
        f"{compose} exec -T backend sh -c 'cd /app && PYTHONPATH=/app python /tmp/_ensure_plan_dispatch_dept_run.py'"
    )
    OUT.write_text("\n".join(log), encoding="utf-8")
    c.close()
    if code != 0:
        raise SystemExit(code)
    for ln in out.splitlines():
        if ln.startswith("RESULT "):
            data = json.loads(ln[7:])
            print("--- decoded ---")
            print("role", data.get("role"))
            print("depts", (data.get("setup") or {}).get("depts"))
            print("apply", (data.get("setup") or {}).get("apply"))
            print("member_count", len(data.get("members") or []))
            print("members", data.get("members"))
            print("key_perms", data.get("key_perms"))
            break
    print("wrote", OUT)


if __name__ == "__main__":
    main()
