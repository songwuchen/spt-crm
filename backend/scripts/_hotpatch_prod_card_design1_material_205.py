#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 补回安排设计1→物料编码边、发布 V12，并修复在途单 SCK00018。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_hotpatch_prod_card_design1_material_205.txt"
CONTAINERS = ["spt-crm-backend-1", "spt-crm-worker-1", "spt-crm-reminder-1"]
FILES = [
    (
        "backend/app/domains/lowcode/workflow_service.py",
        "/app/app/domains/lowcode/workflow_service.py",
    ),
]

ENSURE_PY = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import select, text
from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.approver_resolver import ApprovalContext
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_models import (
    WfNodeInstance, WfProcessDefinition, WfProcessDefinitionVersion,
    WfProcessInstance, WfTaskInstance,
)
from app.domains.lowcode.workflow_service import (
    _flow_missing_prod_card_design1_material_route,
    _published_version,
    _upgrade_drawing_form_flow_if_needed,
)
from app.common.rbac_sync import ensure_prod_material_code_role_members

SERIAL = "SCK00018"
PI = "88dc8ef7-3940-4fce-aa8f-c93bbd6e11d7"
MATERIAL_NODE = "n5"
DESIGN1_NODE = "n17__1"

async def main():
    async with async_session_factory() as db:
        tid = (await db.execute(text("select id from platform_tenants limit 1"))).scalar_one()
        await ensure_prod_material_code_role_members(db, tid)
        await lc.ensure_builtin_form(db, tid, "prod_card_supplement", {"sub": None})
        d = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tid,
            WfProcessDefinition.code == "SYS_PROD_CARD_SUPPLEMENT",
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ))).scalar_one()
        ver0 = await _published_version(db, tid, d.id)
        print("BEFORE v", ver0.version_number, "missing_route",
              _flow_missing_prod_card_design1_material_route(
                  ver0.node_definitions, ver0.route_definitions))
        await _upgrade_drawing_form_flow_if_needed(db, tid, d, "prod_card_supplement")
        await db.commit()
        ver = await _published_version(db, tid, d.id)
        print("AFTER v", ver.version_number, "missing_route",
              _flow_missing_prod_card_design1_material_route(
                  ver.node_definitions, ver.route_definitions))
        design_ids = [n["id"] for n in (ver.node_definitions or [])
                      if isinstance(n, dict) and n.get("name") == "安排设计1"]
        mat_ids = [n["id"] for n in (ver.node_definitions or [])
                   if isinstance(n, dict) and n.get("name") == "物料编码"]
        for r in (ver.route_definitions or []):
            if isinstance(r, dict) and str(r.get("source")) in design_ids and str(r.get("target")) in mat_ids:
                print("ROUTE design1->material", json.dumps(r, ensure_ascii=False))

        inst = await db.get(WfProcessInstance, PI)
        if not inst:
            print("NO_PI", PI)
            return
        fi = await db.get(FormInstance, inst.form_instance_id)
        print("INSTANCE", fi.business_no if fi else None, "pi_status", inst.status,
              "old_ver", inst.process_version_id, "new_ver", ver.id)
        existing = (await db.execute(select(WfNodeInstance).where(
            WfNodeInstance.process_instance_id == inst.id,
            WfNodeInstance.node_def_id == MATERIAL_NODE,
        ))).scalars().all()
        print("EXISTING_MATERIAL_NODES", len(existing))
        if inst.process_version_id != ver.id:
            print("REBIND", inst.process_version_id, "->", ver.id)
            inst.process_version_id = ver.id
        if not existing and inst.status == "running":
            by = {str(n["id"]): n for n in (ver.node_definitions or []) if isinstance(n, dict)}
            node_def = by.get(MATERIAL_NODE)
            if not node_def:
                print("ERROR no material node")
                return
            ctx = ApprovalContext(
                initiator_id=inst.initiator_id or "",
                form_data=dict(fi.form_data or {}) if fi else {},
                nominated=dict(inst.nominated_approvers or {}) or {},
            )
            eng = WorkflowEngine(db, tid)
            print("ACTIVATE", node_def.get("name"), node_def.get("id"))
            await eng._activate_node(inst, ver, node_def, ctx)
            await db.commit()
            print("MATERIAL_ACTIVATED")
        else:
            print("SKIP activate", "existing=", len(existing), "status=", inst.status)
        await db.commit()

        tasks = (await db.execute(select(WfTaskInstance, WfNodeInstance).join(
            WfNodeInstance, WfNodeInstance.id == WfTaskInstance.node_instance_id,
        ).where(
            WfTaskInstance.process_instance_id == inst.id,
            WfTaskInstance.status.in_(["pending", "claimed"]),
        ).order_by(WfTaskInstance.created_at))).all()
        print("PENDING_TASKS", len(tasks))
        for t, ni in tasks:
            print(" ", ni.node_name, ni.node_def_id, t.status, t.assignee_id)

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
        print(text[-6000:] if len(text) > 6000 else text, flush=True)
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

    with sftp.file("/tmp/_ensure_prod_card_design1_material.py", "w") as f:
        f.write(ENSURE_PY)
    sftp.close()

    run(f"echo {PWD} | sudo -S docker restart {' '.join(CONTAINERS)}", timeout=120)
    time.sleep(14)
    run(
        f"echo {PWD} | sudo -S docker cp /tmp/_ensure_prod_card_design1_material.py "
        f"spt-crm-backend-1:/tmp/_ensure_prod_card_design1_material.py",
    )
    run(
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_ensure_prod_card_design1_material.py",
        timeout=180,
    )
    OUT.write_text("\n".join(log), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
