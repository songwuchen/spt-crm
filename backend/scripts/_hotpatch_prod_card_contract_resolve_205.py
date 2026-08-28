#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hotpatch: 生产卡合同 pick 流水号/迁移脏数据解析 + overlay 带出。"""
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

PROBE_PY = r'''
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
from app.database import async_session_factory
from app.domains.lowcode.prod_card_contract_fill import (
    overlay_prod_card_contract_live,
    resolve_prod_card_contract_pick,
)

TID = "00000000-0000-0000-0000-000000000001"
FD = {
    "is_supplement": "否",
    "contract_no_select": "1.2.3-2026082201503",
    "drawing_no_query": {},
}

async def main():
    ref, mode = resolve_prod_card_contract_pick(FD)
    print("pick", ref, mode)
    async with async_session_factory() as db:
        out = await overlay_prod_card_contract_live(db, TID, FD, None)
    print("no_drawing_no", out.get("no_drawing_no"))
    print("yes_customer_name", out.get("yes_customer_name"))
    print("line_items", len(out.get("prod_card_line_items") or []))

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

    with sftp.file("/tmp/_probe_prod_card_contract_resolve.py", "w") as f:
        f.write(PROBE_PY)
    sftp.close()

    run(f"echo {PWD} | sudo -S docker restart spt-crm-backend-1 spt-crm-worker-1 spt-crm-reminder-1", timeout=120)
    import time
    time.sleep(14)
    run(f"echo {PWD} | sudo -S docker cp /tmp/_probe_prod_card_contract_resolve.py spt-crm-backend-1:/tmp/_probe.py")
    run(
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_probe.py",
        timeout=180,
    )
    run("curl -sS -o /tmp/h.txt -w '%{http_code}' http://127.0.0.1:39280/health || true")
    run("cat /tmp/h.txt 2>/dev/null || true")
    c.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
