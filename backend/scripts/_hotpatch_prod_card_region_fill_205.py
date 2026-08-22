#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hotpatch prod_card contract fill + region manager on 205."""
from __future__ import annotations

from pathlib import Path

import paramiko

PWD = "Ruolin2025"
HOST, USER = "192.168.1.205", "swc"
ROOT = Path(r"G:\ruolin-a\spt-crm")

FILES = [
    (
        ROOT / "backend/app/domains/lowcode/prod_card_contract_fill.py",
        "/app/app/domains/lowcode/prod_card_contract_fill.py",
    ),
    (
        ROOT / "backend/app/domains/lowcode/router.py",
        "/app/app/domains/lowcode/router.py",
    ),
]

ENSURE_PY = r'''
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import text
from app.database import async_session_factory
from app.domains.lowcode.service import ensure_builtin_form

TID = "00000000-0000-0000-0000-000000000001"

async def main():
    async with async_session_factory() as db:
        await ensure_builtin_form(db, TID, "prod_card_supplement", {"sub": "00000000-0000-0000-0000-000000000010"})
        await db.commit()
        row = (await db.execute(text("""
            SELECT v.version_number, v.field_definitions
            FROM lc_form_template t
            JOIN lc_form_template_version v
              ON v.template_id = t.id AND v.status = 'published'
            WHERE t.code = 'prod_card_supplement' AND t.tenant_id = :tid
            ORDER BY v.version_number DESC
            LIMIT 1
        """), {"tid": TID})).mappings().first()
        defs = row["field_definitions"] or []
        by = {f.get("id"): f for f in defs if isinstance(f, dict)}
        for fid in ("no_sales_person", "region_manager", "yes_customer_name"):
            f = by.get(fid) or {}
            print(fid, "form_editable=", f.get("form_editable"))

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()

    def run(cmd: str, timeout: int = 180) -> tuple[int, str]:
        print(">>", cmd.replace(PWD, "***")[:220], flush=True)
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        code = o.channel.recv_exit_status()
        text = out + (("\nSTDERR:\n" + err) if err.strip() else "")
        print(text[-2500:] if len(text) > 2500 else text, flush=True)
        print("exit", code, flush=True)
        return code, text

    for local, remote in FILES:
        tmp = f"/tmp/{local.name}"
        with sftp.file(tmp, "w") as f:
            f.write(local.read_text(encoding="utf-8"))
        for ctr in ("spt-crm-backend-1", "spt-crm-worker-1", "spt-crm-reminder-1"):
            run(f"echo {PWD} | sudo -S docker cp {tmp} {ctr}:{remote}")

    with sftp.file("/tmp/_ensure_prod_card_region.py", "w") as f:
        f.write(ENSURE_PY)
    sftp.close()

    run(f"echo {PWD} | sudo -S docker restart spt-crm-backend-1 spt-crm-worker-1 spt-crm-reminder-1", timeout=120)
    import time
    time.sleep(12)
    run(f"echo {PWD} | sudo -S docker cp /tmp/_ensure_prod_card_region.py spt-crm-backend-1:/tmp/_ensure_prod_card_region.py")
    run(
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_ensure_prod_card_region.py",
        timeout=180,
    )
    run("curl -sS -o /tmp/h.txt -w '%{http_code}' http://127.0.0.1:39280/health || true")
    run("cat /tmp/h.txt 2>/dev/null || true")
    c.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
