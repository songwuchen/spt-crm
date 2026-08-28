#!/usr/bin/env python3
"""205: 排查生产卡 SCK00018 流程为何跳过物料编码。"""
from __future__ import annotations

import base64
import json
import paramiko

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"

PY = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import select, text
from app.database import async_session_factory
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.workflow_models import (
    WfProcessInstance, WfTaskInstance, WfProcessDefinitionVersion, WfNodeInstance, WfTaskActionLog,
)

SERIAL = "SCK00018"

async def main():
    async with async_session_factory() as db:
        inst = (await db.execute(
            select(FormInstance).where(
                (FormInstance.business_no == SERIAL)
                | (FormInstance.form_data["serial_no"].astext == SERIAL)
            ).limit(1)
        )).scalar_one_or_none()
        if not inst:
            print("NO_INSTANCE", SERIAL)
            return
        fd = dict(inst.form_data or {})
        print("INSTANCE", inst.id, inst.business_no, inst.status, inst.process_instance_id)
        keys = [
            "serial_no", "is_supplement", "involve_outsource", "is_robot", "need_research_drawing",
            "is_finance_only", "order_type", "is_unit_change", "need_dispatch",
            "design_dispatch", "is_turnkey", "increase_cost", "transfer_packaging_users",
            "design_assignees", "product_type", "involve_amount_change",
        ]
        print("FORM_FLAGS", {k: fd.get(k) for k in keys if k in fd})
        pi = None
        if inst.process_instance_id:
            pi = (await db.execute(
                select(WfProcessInstance).where(WfProcessInstance.id == inst.process_instance_id)
            )).scalar_one_or_none()
        if pi:
            print("PROCESS", pi.id, pi.status, "pending_joins=", pi.pending_joins)
            ver = (await db.execute(
                select(WfProcessDefinitionVersion).where(WfProcessDefinitionVersion.id == pi.process_version_id)
            )).scalar_one_or_none()
            if ver:
                nodes = {n["id"]: n.get("name") for n in (ver.node_definitions or []) if isinstance(n, dict)}
                routes = ver.route_definitions or []
                print("VERSION", ver.version_number, "node_count", len(nodes), "route_count", len(routes))
                ninst = (await db.execute(
                    select(WfNodeInstance).where(WfNodeInstance.process_instance_id == pi.id).order_by(WfNodeInstance.created_at)
                )).scalars().all()
                print("NODE_INSTANCES")
                for ni in ninst:
                    print(" ", ni.status, ni.node_name, ni.node_def_id, str(ni.started_at or "")[:19], str(ni.completed_at or "")[:19])
                tasks = (await db.execute(
                    select(WfTaskInstance).where(WfTaskInstance.process_instance_id == pi.id).order_by(WfTaskInstance.created_at)
                )).scalars().all()
                print("TASKS")
                for t in tasks:
                    ni = next((x for x in ninst if x.id == t.node_instance_id), None)
                    nname = ni.node_name if ni else t.node_instance_id
                    print(" ", t.status, nname, t.assignee_id, str(t.action_at or "")[:19], (t.opinion or "")[:60])
                # routes from 安排设计1
                design_ids = [i for i,n in nodes.items() if n == "安排设计1"]
                mat_ids = [i for i,n in nodes.items() if n == "物料编码"]
                notify_ids = [i for i,n in nodes.items() if n == "通知生产"]
                print("DESIGN1_IDS", design_ids, "MATERIAL_IDS", mat_ids, "NOTIFY_IDS", notify_ids)
                for r in routes:
                    if str(r.get("source")) in design_ids:
                        print("ROUTE_OUT_DESIGN1", "->", nodes.get(str(r.get("target"))), json.dumps({
                            "condition": r.get("condition"), "always": r.get("always"),
                            "fork": r.get("fork"), "exclusive_group": r.get("exclusive_group"),
                        }, ensure_ascii=False))
                for r in routes:
                    if str(r.get("target")) in mat_ids:
                        print("ROUTE_IN_MATERIAL", nodes.get(str(r.get("source"))), "->", "物料编码", json.dumps({
                            "condition": r.get("condition"), "always": r.get("always"),
                            "fork": r.get("fork"), "exclusive_group": r.get("exclusive_group"),
                        }, ensure_ascii=False))
        # audit trail
        rows = (await db.execute(text("""
            SELECT action, actor_name, created_at, opinion
            FROM wf_task_action_log
            WHERE process_instance_id = :pid
            ORDER BY created_at
        """), {"pid": inst.process_instance_id})).all() if inst.process_instance_id else []
        print("ACTION_LOG_COUNT", len(rows))
        for r in rows[-30:]:
            print(" LOG", r[0], r[1], str(r[2])[:19], str(r[3] or "")[:80])

asyncio.run(main())
'''

def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    b64 = base64.b64encode(PY.encode()).decode()
    cmd = (
        f"echo {PWD} | sudo -S docker exec -i -e PYTHONPATH=/app spt-crm-backend-1 "
        f"sh -c 'echo {b64} | base64 -d > /tmp/_diag_sck00018.py && python /tmp/_diag_sck00018.py'"
    )
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR", err[-2000:])
    c.close()


if __name__ == "__main__":
    main()
