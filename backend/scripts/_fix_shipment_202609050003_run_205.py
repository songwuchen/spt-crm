#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"

REMOTE = r'''
import asyncio
from sqlalchemy import text
from app.database import async_session_factory
from app.domains.lowcode.approver_resolver import ApprovalContext
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.workflow_models import WfProcessDefinitionVersion, WfProcessInstance
from app.domains.lowcode.workflow_engine import WorkflowEngine

TENANT = "00000000-0000-0000-0000-000000000001"
PI_ID = "632bdd53-ef83-448d-ab15-39615dbda11a"
FI_ID = "431155ba-6a46-4a55-8dc1-9bf462756be5"

async def main():
    async with async_session_factory() as db:
        inst = await db.get(WfProcessInstance, PI_ID)
        fi = await db.get(FormInstance, FI_ID)
        print("before", inst.status if inst else None, fi.status if fi else None)
        fd = dict(fi.form_data or {})
        if not str(fd.get("is_sales_outbound") or "").strip():
            fd["is_sales_outbound"] = "否"
            fi.form_data = fd
        version = await db.get(WfProcessDefinitionVersion, inst.process_version_id)
        ship_done = next((n for n in (version.node_definitions or []) if n.get("name") == "发货完毕"), None)
        print("ship_done", ship_done["id"] if ship_done else None)
        pending = (await db.execute(text("""
            SELECT t.id::text, t.status, u.real_name, ni.node_name
            FROM wf_task_instance t
            LEFT JOIN users u ON u.id = t.assignee_id
            LEFT JOIN wf_node_instance ni ON ni.id = t.node_instance_id
            WHERE t.process_instance_id = :pid AND t.status IN ('pending','waiting')
        """), {"pid": PI_ID})).mappings().all()
        if pending:
            print("already pending", [dict(x) for x in pending])
            return
        if inst.status == "completed":
            inst.status = "running"
            inst.completed_at = None
            fi.status = "submitted"
            pj = list(inst.pending_joins or [])
            nid = ship_done["id"]
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
        if inst.status == "running" and not await eng._has_live_work(inst):
            await eng._activate_node(inst, version, ship_done, ctx)
        await eng.flush_notifications()
        await db.commit()
        after = (await db.execute(text("""
            SELECT t.id::text, t.status, u.real_name AS assignee, ni.node_name
            FROM wf_task_instance t
            LEFT JOIN users u ON u.id = t.assignee_id
            LEFT JOIN wf_node_instance ni ON ni.id = t.node_instance_id
            WHERE t.process_instance_id = :pid
            ORDER BY t.created_at DESC LIMIT 5
        """), {"pid": PI_ID})).mappings().all()
        await db.refresh(inst)
        await db.refresh(fi)
        print("after", inst.status, fi.status)
        print("tasks", [dict(x) for x in after])

asyncio.run(main())
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
b64 = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
_, o, e = c.exec_command(
    f"echo {PWD} | sudo -S bash -lc "
    f"'echo {b64} | base64 -d > /tmp/_fix_ship2.py && "
    f"cat /tmp/_fix_ship2.py | docker exec -i spt-crm-backend-1 python -'",
    timeout=120,
)
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace")[-2500:])
c.close()
