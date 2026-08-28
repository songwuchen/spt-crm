#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205：安装图设计通知抄送设计指派1/2 改为曹修国+订货人+设计指派+发起人。"""
from __future__ import annotations

import time
from pathlib import Path

import paramiko

PWD = "Ruolin2025"
HOST, USER = "192.168.1.205", "swc"
ROOT = Path(r"G:\ruolin-a\spt-crm")
OUT = ROOT / "_hotpatch_install_drawing_cc_design_assign_205.txt"

LOCAL_FILE = ROOT / "backend/app/domains/lowcode/workflow_service.py"
REMOTE_FILE = "/app/app/domains/lowcode/workflow_service.py"
CONTAINERS = ("spt-crm-backend-1", "spt-crm-worker-1", "spt-crm-reminder-1")

ENSURE_PY = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import select, text
from app.database import async_session_factory
from app.domains.lowcode.workflow_models import WfProcessDefinition
from app.domains.lowcode.workflow_service import _upgrade_drawing_form_flow_if_needed

TID = "00000000-0000-0000-0000-000000000001"

async def main():
    async with async_session_factory() as db:
        d = (await db.execute(
            select(WfProcessDefinition).where(
                WfProcessDefinition.tenant_id == TID,
                WfProcessDefinition.code == "SYS_INSTALL_DRAWING_NOTICE",
                WfProcessDefinition.is_deleted == False,  # noqa: E712
            ).limit(1)
        )).scalar_one_or_none()
        print("def", d.id if d else None, d.current_version if d else None)
        if d:
            await _upgrade_drawing_form_flow_if_needed(db, TID, d, "install_drawing_notice")
        await db.commit()
        row = (await db.execute(text("""
            SELECT v.version_number,
                   (SELECT jsonb_agg(jsonb_build_object(
                      'id', n->>'id', 'name', n->>'name',
                      'rule', n->'approver_rule'
                    ) ORDER BY n->>'name')
                    FROM jsonb_array_elements(v.node_definitions) n
                    WHERE n->>'type'='cc'
                      AND n->>'name' IN ('抄送设计指派1', '抄送设计指派2')) AS cc_nodes
            FROM wf_process_definition d
            JOIN wf_process_definition_version v
              ON v.process_definition_id = d.id AND v.status='published'
            WHERE d.tenant_id=:tid AND d.code='SYS_INSTALL_DRAWING_NOTICE'
            ORDER BY v.version_number DESC LIMIT 1
        """), {"tid": TID})).mappings().first()
        if row:
            print("version", row["version_number"])
            print(json.dumps(row["cc_nodes"], ensure_ascii=False, indent=2))

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
        text = out + (("\nSTDERR:\n" + err) if err.strip() else "")
        print(text[-4000:] if len(text) > 4000 else text, flush=True)
        log.append(f"\n=== {cmd}\n{text}\n")
        return text

    tmp = "/tmp/workflow_service.py"
    with sftp.file(tmp, "w") as f:
        f.write(LOCAL_FILE.read_text(encoding="utf-8"))
    with sftp.file("/tmp/_ensure_install_drawing_cc.py", "w") as f:
        f.write(ENSURE_PY)
    sftp.close()

    for ctr in CONTAINERS:
        run(f"echo {PWD} | sudo -S docker cp {tmp} {ctr}:{REMOTE_FILE}")

    run(
        f"echo {PWD} | sudo -S docker restart {' '.join(CONTAINERS)}",
        timeout=120,
    )
    time.sleep(14)
    run(
        "echo {pwd} | sudo -S docker cp /tmp/_ensure_install_drawing_cc.py "
        "spt-crm-backend-1:/tmp/_ensure_install_drawing_cc.py".format(pwd=PWD)
    )
    run(
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_ensure_install_drawing_cc.py",
        timeout=300,
    )
    run("curl -sS http://127.0.0.1:39280/health || true")
    c.close()
    OUT.write_text("".join(log), encoding="utf-8")
    print("WROTE", OUT, flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
