#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从版本历史恢复用户在设计器编排的流程，并同步到 205。"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SUDO = f"echo {PWD} | sudo -S"
TID = "00000000-0000-0000-0000-000000000001"
ROOT = Path(r"G:\ruolin-a\spt-crm")
EXPORT = ROOT / "_tech_fb_outsource_user_restored_export.json"
OUT = ROOT / "_tech_fb_outsource_user_restored_out.txt"

# 用户在设计器保存后被系统自动覆盖前的版本
RESTORE = {
    "tech_agreement_feedback": {
        "wf_code": "SYS_TECH_AGREEMENT_FEEDBACK",
        "from_version": 3,
    },
    "contract_outsource_early": {
        "wf_code": "SYS_CONTRACT_OUTSOURCE_EARLY",
        "from_version": 7,
    },
}


def uid() -> str:
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


async def restore_local() -> dict:
    from sqlalchemy import text

    from app.database import async_session_factory

    out: dict = {}
    async with async_session_factory() as db:
        for form_code, spec in RESTORE.items():
            wf_code = spec["wf_code"]
            ver = spec["from_version"]
            d = (
                await db.execute(
                    text(
                        "SELECT id, current_version FROM wf_process_definition "
                        "WHERE tenant_id = :t AND code = :c AND is_deleted = false"
                    ),
                    {"t": TID, "c": wf_code},
                )
            ).mappings().one()
            src = (
                await db.execute(
                    text(
                        "SELECT node_definitions, route_definitions "
                        "FROM wf_process_definition_version "
                        "WHERE process_definition_id = :did AND version_number = :v "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"did": d["id"], "v": ver},
                )
            ).mappings().first()
            if not src:
                raise RuntimeError(f"missing history version {form_code} v{ver}")
            nodes = copy.deepcopy(src["node_definitions"] or [])
            routes = copy.deepcopy(src["route_definitions"] or [])
            mx = (
                await db.execute(
                    text(
                        "SELECT coalesce(max(version_number), 0) FROM wf_process_definition_version "
                        "WHERE process_definition_id = :did"
                    ),
                    {"did": d["id"]},
                )
            ).scalar()
            next_wv = max(int(d["current_version"] or 0) + 1, int(mx) + 1)
            await db.execute(
                text(
                    "UPDATE wf_process_definition_version SET status = 'deprecated', updated_at = now() "
                    "WHERE process_definition_id = :did AND status = 'published'"
                ),
                {"did": d["id"]},
            )
            await db.execute(
                text(
                    "INSERT INTO wf_process_definition_version("
                    "  id, tenant_id, process_definition_id, version_number,"
                    "  node_definitions, route_definitions, approver_rules, status,"
                    "  published_at, created_at, updated_at"
                    ") VALUES ("
                    "  :id, :t, :did, :vn,"
                    "  CAST(:nodes AS jsonb), CAST(:routes AS jsonb), '[]'::jsonb, 'published',"
                    "  :pub, :pub, :pub"
                    ")"
                ),
                {
                    "id": uid(),
                    "t": TID,
                    "did": d["id"],
                    "vn": next_wv,
                    "nodes": json.dumps(nodes, ensure_ascii=False),
                    "routes": json.dumps(routes, ensure_ascii=False),
                    "pub": now(),
                },
            )
            await db.execute(
                text(
                    "UPDATE wf_process_definition "
                    "SET current_version = :vn, status = 'published', category = 'user_designed', "
                    "updated_at = now() "
                    "WHERE id = :did"
                ),
                {"vn": next_wv, "did": d["id"]},
            )
            names = [n.get("name") for n in nodes if isinstance(n, dict)]
            print(
                f"RESTORED local {form_code} v{ver} -> v{next_wv} "
                f"nodes={len(nodes)} routes={len(routes)}",
                flush=True,
            )
            print(f"  {names}", flush=True)
            out[form_code] = {
                "wf_code": wf_code,
                "from_version": ver,
                "version_number": next_wv,
                "node_definitions": nodes,
                "route_definitions": routes,
            }
        await db.commit()
    EXPORT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {EXPORT}", flush=True)
    return out


APPLY = r"""
# -*- coding: utf-8 -*-
import asyncio
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import async_session_factory

TID = "00000000-0000-0000-0000-000000000001"
DATA = json.load(open("/tmp/_tech_fb_outsource_user_restored_export.json", encoding="utf-8"))


def uid() -> str:
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


async def publish_flow(wf_code: str, nodes: list, routes: list) -> dict:
    async with async_session_factory() as db:
        d = (
            await db.execute(
                text(
                    "SELECT id, current_version FROM wf_process_definition "
                    "WHERE tenant_id = :t AND code = :c AND is_deleted = false"
                ),
                {"t": TID, "c": wf_code},
            )
        ).mappings().one()
        mx = (
            await db.execute(
                text(
                    "SELECT coalesce(max(version_number), 0) FROM wf_process_definition_version "
                    "WHERE process_definition_id = :did"
                ),
                {"did": d["id"]},
            )
        ).scalar()
        next_wv = max(int(d["current_version"] or 0) + 1, int(mx) + 1)
        await db.execute(
            text(
                "UPDATE wf_process_definition_version SET status = 'deprecated', updated_at = now() "
                "WHERE process_definition_id = :did AND status = 'published'"
            ),
            {"did": d["id"]},
        )
        await db.execute(
            text(
                "INSERT INTO wf_process_definition_version("
                "  id, tenant_id, process_definition_id, version_number,"
                "  node_definitions, route_definitions, approver_rules, status,"
                "  published_at, created_at, updated_at"
                ") VALUES ("
                "  :id, :t, :did, :vn,"
                "  CAST(:nodes AS jsonb), CAST(:routes AS jsonb), CAST(:rules AS jsonb), 'published',"
                "  :pub, :pub, :pub"
                ")"
            ),
            {
                "id": uid(),
                "t": TID,
                "did": d["id"],
                "vn": next_wv,
                "nodes": json.dumps(nodes, ensure_ascii=False),
                "routes": json.dumps(routes, ensure_ascii=False),
                "rules": "[]",
                "pub": now(),
            },
        )
        await db.execute(
            text(
                "UPDATE wf_process_definition "
                "SET current_version = :vn, status = 'published', category = 'user_designed', "
                "updated_at = now() "
                "WHERE id = :did"
            ),
            {"vn": next_wv, "did": d["id"]},
        )
        names = (
            await db.execute(
                text(
                    "SELECT n->>'name' AS name FROM wf_process_definition d "
                    "JOIN wf_process_definition_version v ON v.process_definition_id = d.id AND v.status = 'published' "
                    "CROSS JOIN LATERAL jsonb_array_elements(v.node_definitions) n "
                    "WHERE d.id = :did"
                ),
                {"did": d["id"]},
            )
        ).scalars().all()
        await db.commit()
        return {"wf_code": wf_code, "version": next_wv, "names": list(names)}


async def main() -> None:
    for form_code, payload in DATA.items():
        r = await publish_flow(
            payload["wf_code"],
            payload["node_definitions"],
            payload["route_definitions"],
        )
        print("205", form_code, r, flush=True)


asyncio.run(main())
"""


def apply_remote() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    log: list[str] = []

    def run(cmd: str, timeout: int = 300) -> tuple[int, str]:
        print(">>", cmd.replace(PWD, "***")[:220], flush=True)
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        code = o.channel.recv_exit_status()
        text = out + (("\nSTDERR:\n" + err) if err.strip() else "")
        print(text[-8000:] if len(text) > 8000 else text, flush=True)
        log.append(text)
        return code, text

    sftp = c.open_sftp()
    sftp.put(str(EXPORT), "/tmp/_tech_fb_outsource_user_restored_export.json")
    with sftp.file("/tmp/_apply_user_flows_restore.py", "w") as f:
        f.write(APPLY)
    sftp.close()

    run(
        f"{SUDO} docker cp /tmp/_tech_fb_outsource_user_restored_export.json "
        "spt-crm-backend-1:/tmp/_tech_fb_outsource_user_restored_export.json"
    )
    run(f"{SUDO} docker cp /tmp/_apply_user_flows_restore.py spt-crm-backend-1:/tmp/_apply_user_flows_restore.py")
    code, _ = run(
        f"{SUDO} docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        "python /tmp/_apply_user_flows_restore.py",
        timeout=300,
    )
    OUT.write_text("\n".join(log), encoding="utf-8")
    c.close()
    if code != 0:
        raise SystemExit(code)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(restore_local())
    apply_remote()
    print("RESTORE+SYNC OK", flush=True)


if __name__ == "__main__":
    main()
