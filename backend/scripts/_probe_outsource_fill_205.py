#!/usr/bin/env python3
"""205: 排查外购件选生产卡后 office/design_assign 带出。"""
from __future__ import annotations

import json
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SUDO = f"echo {PWD} | sudo -S"
FI_ID = "c87929b8-3bc4-41a7-b978-d13e34a9c558"
TID = "00000000-0000-0000-0000-000000000001"

INNER = f'''
import asyncio, json
from app.database import async_session_factory
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.pricing_checklist_fields import (
    build_contract_outsource_prod_card_fill,
    list_pickable_form_instances,
)

async def main():
    async with async_session_factory() as db:
        fi = await db.get(FormInstance, "{FI_ID}")
        fd = fi.form_data or {{}}
        for k in ("offices", "office", "design_assignees", "design_assign"):
            print("PC", k, repr(fd.get(k)))
        data = await list_pickable_form_instances(
            db, "{TID}", form_code="prod_card_supplement",
            link_field="link_prod_card", keyword="WMGF202608141", page=1, page_size=5,
        )
        for it in data.get("items") or []:
            print("PICK_FILL", json.dumps(it.get("fill"), ensure_ascii=False))
            print("PICK_COLS", json.dumps(it.get("cols"), ensure_ascii=False))

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_probe_outsource_fill.py", "w") as f:
        f.write(INNER)
    sftp.close()
    _, o, e = c.exec_command(
        f"{SUDO} docker cp /tmp/_probe_outsource_fill.py spt-crm-backend-1:/tmp/_probe_outsource_fill.py && "
        f"{SUDO} docker exec -e PYTHONPATH=/app spt-crm-backend-1 python /tmp/_probe_outsource_fill.py",
        timeout=120,
    )
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err)
    c.close()


if __name__ == "__main__":
    main()
