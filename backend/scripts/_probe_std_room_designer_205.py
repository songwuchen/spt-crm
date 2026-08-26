# -*- coding: utf-8 -*-
import paramiko

PWD = "Ruolin2025"
HOST, USER = "192.168.1.205", "swc"
SUDO = f"echo {PWD} | sudo -S"

INNER = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import text
from app.database import async_session_factory

TID = "00000000-0000-0000-0000-000000000001"

async def main():
    async with async_session_factory() as db:
        did = (await db.execute(text(
            "SELECT id, path FROM departments WHERE tenant_id=:t AND name='中央研究院' ORDER BY path LIMIT 5"
        ), {"t": TID})).mappings().all()
        print("depts", json.dumps([dict(r) for r in did], ensure_ascii=False))
        from app.domains.lowcode.prod_card_contract_fill import resolve_prod_card_std_room_designer_dept_id
        print("resolved", await resolve_prod_card_std_room_designer_dept_id(db, TID))
        from app.domains.lowcode.service import ensure_builtin_form, get_published_version
        SUB = {"sub": "00000000-0000-0000-0000-000000000010", "real_name": "热更新", "username": "hotpatch"}
        tpl = await ensure_builtin_form(db, TID, "prod_card_supplement", SUB)
        print("template", tpl.code, "ver", tpl.current_version)
        ver = await get_published_version(db, TID, tpl.id)
        for f in (ver.field_definitions if ver else []) or []:
            if f.get("id") != "std_room_fill":
                continue
            for col in f.get("detail_table_columns") or []:
                if col.get("id") == "designer":
                    print(json.dumps({
                        "designer_pickable_scope": (col.get("props") or {}).get("pickable_scope"),
                    }, ensure_ascii=False))

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_probe_std_designer.py", "w") as f:
        f.write(INNER)
    sftp.close()
    cmd = (
        f"{SUDO} docker cp /tmp/_probe_std_designer.py spt-crm-backend-1:/tmp/_probe_std_designer.py ; "
        f"{SUDO} docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 python /tmp/_probe_std_designer.py"
    )
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR", err[-800:])
    c.close()


if __name__ == "__main__":
    main()
