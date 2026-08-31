#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 合同评审「财务总监意见」节点可填图纸编号/意见执行情况。"""
from __future__ import annotations

import time
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
ROOT = Path(r"G:\ruolin-a\spt-crm")
SUDO = f"echo {PWD} | sudo -S"

UPGRADE_PY = r'''
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import select, text
from app.database import async_session_factory
from app.domains.lowcode.workflow_models import WfProcessDefinition
from app.domains.lowcode.workflow_service import (
    _upgrade_contract_review_jdy_if_needed,
    _published_version,
)

async def main():
    async with async_session_factory() as db:
        tid = (await db.execute(text("select id from platform_tenants limit 1"))).scalar_one()
        d = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tid,
            WfProcessDefinition.biz_type == "contract_review",
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ))).scalar_one_or_none()
        if not d:
            print("NO_DEF")
            return
        ver_before = await _published_version(db, tid, d.id)
        print("BEFORE v", ver_before.version_number if ver_before else None)
        await _upgrade_contract_review_jdy_if_needed(db, tid, d)
        await db.commit()
        ver_after = await _published_version(db, tid, d.id)
        print("AFTER v", ver_after.version_number if ver_after else None)
        if ver_after:
            by_id = {n.get("id"): n for n in (ver_after.node_definitions or []) if isinstance(n, dict)}
            fp = {p.get("field") for p in (by_id.get("approval_finance_dir") or {}).get("field_perms") or []}
            print("FIN_DIR_FIELDS", sorted(fp))

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)

    def sudo(cmd: str, timeout: int = 600) -> None:
        print(">>", cmd.replace(PWD, "***")[:200], flush=True)
        _, o, e = c.exec_command(f"{SUDO} bash -lc {repr(cmd)}", timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        print(out, flush=True)
        if err.strip():
            print(err[-800:], flush=True)
        print("exit", o.channel.recv_exit_status(), flush=True)

    rel = "app/domains/lowcode/workflow_service.py"
    local = ROOT / "backend" / rel
    sftp = c.open_sftp()
    remote = "/tmp/workflow_service.py"
    sftp.put(str(local), remote)
    with sftp.file("/tmp/_upgrade_cr_finance_signing.py", "w") as f:
        f.write(UPGRADE_PY)
    sftp.close()

    for box in ("spt-crm-backend-1", "spt-crm-worker-1", "spt-crm-reminder-1"):
        sudo(f"docker cp {remote} {box}:/app/{rel}")
    sudo("docker cp /tmp/_upgrade_cr_finance_signing.py spt-crm-backend-1:/tmp/_upgrade_cr_finance_signing.py")
    sudo("cd /home/swc/spt-crm && docker compose --env-file .env restart backend worker reminder", timeout=180)
    time.sleep(10)
    sudo(
        "docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        "python /tmp/_upgrade_cr_finance_signing.py",
        timeout=120,
    )
    c.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
