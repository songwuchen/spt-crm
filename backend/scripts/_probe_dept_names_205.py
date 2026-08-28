#!/usr/bin/env python3
"""205: 查设计二室/电气组部门 id。"""
from __future__ import annotations

import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8")
HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SUDO = f"echo {PWD} | sudo -S"
INNER = '''
import asyncio
from sqlalchemy import text
from app.database import async_session_factory

async def main():
    async with async_session_factory() as db:
        rows = (await db.execute(text(
            "SELECT id, name, path FROM departments "
            "WHERE name IN ('设计二室', '电气组') ORDER BY name, path"
        ))).all()
        for r in rows:
            print(r)

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_p.py", "w") as f:
        f.write(INNER)
    sftp.close()
    _, o, e = c.exec_command(
        f"{SUDO} docker cp /tmp/_p.py spt-crm-backend-1:/tmp/_p.py && "
        f"{SUDO} docker exec -e PYTHONPATH=/app spt-crm-backend-1 python /tmp/_p.py",
        timeout=60,
    )
    print(o.read().decode())
    c.close()


if __name__ == "__main__":
    main()
