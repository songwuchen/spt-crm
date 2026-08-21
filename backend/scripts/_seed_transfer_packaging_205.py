#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 补齐「转新乡、工艺包装」可选范围成员（fa-zxxgy）。"""
from __future__ import annotations

import paramiko

PWD = "Ruolin2025"
PY = r'''
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
from app.database import async_session_factory
from app.domains.organization.pickable_scope_service import (
    TRANSFER_PACKAGING_MEMBER_NAMES,
    ensure_preset_scopes,
    get_scope_by_code,
    department_names_by_user_ids,
)
from app.domains.auth.models import User
from sqlalchemy import select

TID = "00000000-0000-0000-0000-000000000001"

async def main():
    async with async_session_factory() as db:
        await ensure_preset_scopes(db, TID)
        await db.commit()
        scope = await get_scope_by_code(db, TID, "fa-zxxgy")
        uids = (scope.rules or {}).get("user_ids") or []
        rows = (await db.execute(
            select(User.id, User.real_name).where(User.id.in_(uids))
        )).all() if uids else []
        name_by_id = {str(i): n for i, n in rows}
        print("canonical:", list(TRANSFER_PACKAGING_MEMBER_NAMES))
        print("fa-zxxgy members:", [name_by_id.get(str(u), u) for u in uids])
        missing = [n for n in TRANSFER_PACKAGING_MEMBER_NAMES if n not in name_by_id.values()]
        if missing:
            print("MISSING in CRM users:", missing)
            # fuzzy probe
            for n in missing:
                hits = (await db.execute(
                    select(User.real_name, User.username).where(
                        User.tenant_id == TID, User.is_active.is_(True),
                        User.real_name.ilike(f"%{n[:2]}%"),
                    ).limit(8)
                )).all()
                if hits:
                    print("  probe", n, "->", hits)

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.1.205", username="swc", password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_seed_fa_zxxgy_205.py", "w") as f:
        f.write(PY)
    sftp.close()
    remote = "backend/app/domains/organization/pickable_scope_service.py"
    local = __file__.replace("\\", "/").rsplit("/", 2)[0] + "/../app/domains/organization/pickable_scope_service.py"
    import os
    local_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "app", "domains", "organization", "pickable_scope_service.py"))
    with open(local_path, "rb") as lf:
        content = lf.read()
    sftp = c.open_sftp()
    with sftp.file(f"/tmp/pickable_scope_service.py", "wb") as rf:
        rf.write(content)
    sftp.close()
    cmds = [
        f"echo {PWD} | sudo -S docker cp /tmp/pickable_scope_service.py spt-crm-backend-1:/app/app/domains/organization/pickable_scope_service.py",
        f"echo {PWD} | sudo -S docker cp /tmp/_seed_fa_zxxgy_205.py spt-crm-backend-1:/tmp/_seed_fa_zxxgy_205.py",
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 python /tmp/_seed_fa_zxxgy_205.py",
    ]
    for cmd in cmds:
        print(">>", cmd.replace(PWD, "***")[:160], flush=True)
        _, o, e = c.exec_command(cmd, timeout=180)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        if out.strip():
            print(out, flush=True)
        if err.strip():
            print("STDERR", err[-800:], flush=True)
        if o.channel.recv_exit_status():
            raise SystemExit(1)
    c.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
