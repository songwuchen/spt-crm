#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205：热补发货通知汇聚修复 + 重开 24.1-202609050003 补「发货完毕」待办给段尉利。"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
ROOT = Path(__file__).resolve().parents[2]
SUDO = f"echo {PWD} | sudo -S"
OUT = ROOT / "_fix_shipment_202609050003_205.txt"

BE_FILES = [
    "app/domains/lowcode/workflow_engine.py",
    "app/domains/lowcode/shipment_notice_fields.py",
]

REMOTE_FIX = r'''
# -*- coding: utf-8 -*-
import asyncio
from sqlalchemy import select, text

from app.database import async_session_factory
from app.domains.lowcode.approver_resolver import ApprovalContext
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.workflow_models import WfProcessDefinitionVersion, WfProcessInstance
from app.domains.lowcode.workflow_engine import WorkflowEngine

TENANT = "00000000-0000-0000-0000-000000000001"
PI_ID = "632bdd53-ef83-448d-ab15-39615dbda11a"
FI_ID = "431155ba-6a46-4a55-8dc1-9bf462756be5"
BUSINESS_NO = "24.1-202609050003"


async def main():
    async with async_session_factory() as db:
        inst = await db.get(WfProcessInstance, PI_ID)
        fi = await db.get(FormInstance, FI_ID)
        if not inst or not fi:
            print("MISSING inst/fi")
            return
        print("before", inst.status, fi.status, inst.completed_at)

        # 补表单默认值，便于后续选路
        fd = dict(fi.form_data or {})
        if not str(fd.get("is_sales_outbound") or "").strip():
            fd["is_sales_outbound"] = "否"
            fi.form_data = fd

        version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
        nodes = version.node_definitions or []
        ship_done = next((n for n in nodes if n.get("name") == "发货完毕"), None)
        if not ship_done:
            print("NO_SHIP_DONE_NODE")
            return
        nid = ship_done["id"]
        print("ship_done_node", nid)

        existing = (await db.execute(text("""
            SELECT id::text, status FROM wf_node_instance
            WHERE process_instance_id = :pid AND node_def_id = :nid
            ORDER BY started_at DESC LIMIT 1
        """), {"pid": PI_ID, "nid": nid})).mappings().first()
        print("existing_ni", dict(existing) if existing else None)

        pending_task = (await db.execute(text("""
            SELECT t.id::text, t.status, u.real_name
            FROM wf_task_instance t
            LEFT JOIN users u ON u.id = t.assignee_id
            WHERE t.process_instance_id = :pid AND t.status IN ('pending','waiting')
            ORDER BY t.created_at DESC LIMIT 3
        """), {"pid": PI_ID})).mappings().all()
        print("pending_tasks", [dict(x) for x in pending_task])
        if pending_task:
            print("ALREADY_HAS_PENDING")
            await db.commit()
            return

        if inst.status == "completed":
            inst.status = "running"
            inst.completed_at = None
            fi.status = "submitted"
            pj = list(inst.pending_joins or [])
            if not any(isinstance(x, dict) and x.get("pending_convergence") == nid for x in pj):
                pj.append({"pending_convergence": nid})
            inst.pending_joins = pj

        eng = WorkflowEngine(db, TENANT)
        ctx = ApprovalContext(
            initiator_id=inst.initiator_id,
            form_data=await eng._form_data(inst),
            nominated=inst.nominated_approvers or {},
        )
        await eng._try_activate_pending_convergence(inst, version, ctx)
        if inst.status == "running":
            live = await eng._has_live_work(inst)
            if not live:
                await eng._activate_node(inst, version, ship_done, ctx)

        await eng.flush_notifications()
        await db.commit()
        await db.refresh(inst)
        await db.refresh(fi)

        after = (await db.execute(text("""
            SELECT t.id::text, t.status, u.real_name AS assignee, ni.node_name
            FROM wf_task_instance t
            LEFT JOIN users u ON u.id = t.assignee_id
            LEFT JOIN wf_node_instance ni ON ni.id = t.node_instance_id
            WHERE t.process_instance_id = :pid
            ORDER BY t.created_at DESC LIMIT 5
        """), {"pid": PI_ID})).mappings().all()
        print("after", inst.status, fi.status)
        print("tasks", [dict(x) for x in after])


asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)

    def sudo(cmd: str, timeout: int = 300) -> int:
        print(">>", cmd[:200], flush=True)
        _, o, e = c.exec_command(f"{SUDO} bash -lc {repr(cmd)}", timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        code = o.channel.recv_exit_status()
        text = out + (("\n" + err) if err.strip() else "")
        OUT.write_text(text, encoding="utf-8")
        print(text[-3000:], flush=True)
        return code

    sftp = c.open_sftp()
    for rel in BE_FILES:
        local = ROOT / "backend" / rel
        remote = f"/tmp/{Path(rel).name}"
        sftp.put(str(local), remote)
        for ctr in ("spt-crm-backend-1", "spt-crm-worker-1"):
            sudo(f"docker cp {remote} {ctr}:/app/{rel} || true")
    sftp.close()

    sudo("docker restart spt-crm-backend-1 spt-crm-worker-1 2>/dev/null; sleep 5")

    b64 = base64.b64encode(REMOTE_FIX.encode("utf-8")).decode("ascii")
    sudo(
        f"echo {b64} | base64 -d > /tmp/_fix_ship_050003.py && "
        f"cat /tmp/_fix_ship_050003.py | docker exec -i spt-crm-backend-1 python -"
    )
    c.close()


if __name__ == "__main__":
    main()
