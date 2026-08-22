# -*- coding: utf-8 -*-
"""205: 同步 legal 角色（24.2.3合同/项目评审-法务审批多人）及成员。"""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SUDO = f"echo {PWD} | sudo -S"
TENANT = "00000000-0000-0000-0000-000000000001"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_sync_legal_role_205_out.txt"

INNER = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
import app.domains.auth.models  # noqa: F401
import app.domains.organization.models  # noqa: F401
from sqlalchemy import text
from app.database import async_session_factory
from app.common.rbac_sync import ensure_legal_role_members

TENANT = "%s"

async def main():
    async with async_session_factory() as db:
        result = await ensure_legal_role_members(db, TENANT)
        await db.commit()
        print("ensure:", json.dumps(result, ensure_ascii=False, default=str))
        row = (await db.execute(text("""
            SELECT r.code, r.name, count(ur.user_id) AS n,
                   coalesce(string_agg(u.real_name, ',' ORDER BY u.real_name), '') AS members
            FROM roles r
            LEFT JOIN user_roles ur ON ur.role_id = r.id AND ur.tenant_id = r.tenant_id
            LEFT JOIN users u ON u.id = ur.user_id
            WHERE r.tenant_id = :t AND r.code = 'legal'
            GROUP BY r.code, r.name
        """), {"t": TENANT})).mappings().first()
        print("AFTER:", json.dumps(dict(row or {}), ensure_ascii=False))

asyncio.run(main())
''' % TENANT

COPY_FILES = [
    ("backend/app/common/rbac_catalog.py", "/app/app/common/rbac_catalog.py"),
    ("backend/app/common/rbac_sync.py", "/app/app/common/rbac_sync.py"),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    log: list[str] = []

    def run(cmd: str, timeout: int = 300) -> tuple[int, str]:
        print(">>", cmd.replace(PWD, "***")[:220], flush=True)
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        code = o.channel.recv_exit_status()
        text = out + (("\nSTDERR:\n" + err) if err.strip() else "")
        print(text[-4000:] if len(text) > 4000 else text, flush=True)
        log.append(f"=== {cmd}\n{text}\nexit={code}\n")
        return code, text

    sftp = c.open_sftp()
    for rel, remote in COPY_FILES:
        local = ROOT / rel
        tmp = f"/tmp/{local.name}"
        sftp.put(str(local), tmp)
        run(f"{SUDO} docker cp {tmp} spt-crm-backend-1:{remote}")
    with sftp.file("/tmp/_sync_legal_role.py", "w") as f:
        f.write(INNER)
    sftp.close()

    run(f"{SUDO} docker cp /tmp/_sync_legal_role.py spt-crm-backend-1:/tmp/_sync_legal_role.py")
    code, _ = run(
        f"{SUDO} docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_sync_legal_role.py",
        timeout=300,
    )
    OUT.write_text("".join(log), encoding="utf-8")
    c.close()
    if code != 0:
        raise SystemExit(code)
    print("OK wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
