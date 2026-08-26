#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205 + 本地逻辑：标准化室子表「设计人」限定中央研究院（含下级）。"""
from __future__ import annotations

import time
from pathlib import Path

import paramiko

PWD = "Ruolin2025"
HOST, USER = "192.168.1.205", "swc"
ROOT = Path(r"G:\ruolin-a\spt-crm")
OUT = ROOT / "_hotpatch_prod_card_std_room_designer_scope_205.txt"

FILES = (
    ("backend/app/domains/lowcode/prod_card_contract_fill.py", "/app/app/domains/lowcode/prod_card_contract_fill.py"),
    ("backend/app/domains/lowcode/service.py", "/app/app/domains/lowcode/service.py"),
)
CONTAINERS = ("spt-crm-backend-1", "spt-crm-worker-1", "spt-crm-reminder-1")

ENSURE_PY = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
import app.domains.auth.models  # noqa: F401
import app.domains.organization.models  # noqa: F401
from app.database import async_session_factory
from app.domains.lowcode.service import ensure_builtin_form

TID = "00000000-0000-0000-0000-000000000001"
SUB = {"sub": "00000000-0000-0000-0000-000000000010", "real_name": "热更新", "username": "hotpatch"}

async def main():
    async with async_session_factory() as db:
        from app.domains.lowcode.prod_card_contract_fill import resolve_prod_card_std_room_designer_dept_id
        did = await resolve_prod_card_std_room_designer_dept_id(db, TID)
        print("research_dept_id", did)
        tpl = await ensure_builtin_form(db, TID, "prod_card_supplement", SUB)
        print("template", tpl.code, "ver", tpl.current_version)
        from app.domains.lowcode.service import get_published_version
        ver = await get_published_version(db, TID, tpl.id)
        defs = (ver.field_definitions if ver else []) or []
        for f in defs:
            if not isinstance(f, dict) or f.get("id") != "std_room_fill":
                continue
            for col in f.get("detail_table_columns") or []:
                if col.get("id") == "designer":
                    print(json.dumps({
                        "designer_pickable_scope": (col.get("props") or {}).get("pickable_scope"),
                    }, ensure_ascii=False))

asyncio.run(main())
'''


def main() -> None:
    log: list[str] = []
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST, username=USER, password=PWD,
        timeout=60, banner_timeout=60, auth_timeout=60,
        look_for_keys=False, allow_agent=False,
    )
    sftp = c.open_sftp()

    def run(cmd: str, timeout: int = 300) -> str:
        print(">>", cmd.replace(PWD, "***")[:220], flush=True)
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        code = o.channel.recv_exit_status()
        text = out + (("\nSTDERR:\n" + err) if err.strip() else "")
        log.append(f"$ {cmd}\n{text}\nexit={code}\n")
        print(text[-4000:] if len(text) > 4000 else text, flush=True)
        if code != 0:
            raise SystemExit(code)
        return text

    for rel, remote in FILES:
        local = ROOT / rel
        tmp = f"/tmp/{local.name}"
        with sftp.file(tmp, "w") as f:
            f.write(local.read_text(encoding="utf-8"))
        for ctr in CONTAINERS:
            run(f"echo {PWD} | sudo -S docker cp {tmp} {ctr}:{remote}")

    with sftp.file("/tmp/_ensure_prod_card_std_room_designer.py", "w") as f:
        f.write(ENSURE_PY)
    sftp.close()

    run(f"echo {PWD} | sudo -S docker restart {' '.join(CONTAINERS)}", timeout=120)
    time.sleep(14)
    run(
        f"echo {PWD} | sudo -S docker cp /tmp/_ensure_prod_card_std_room_designer.py "
        f"spt-crm-backend-1:/tmp/_ensure_prod_card_std_room_designer.py",
    )
    run(
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_ensure_prod_card_std_room_designer.py",
        timeout=180,
    )
    OUT.write_text("\n".join(log), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
