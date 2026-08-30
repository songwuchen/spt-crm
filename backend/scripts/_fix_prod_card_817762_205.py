#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 补开 1.2.817762「安排设计1」后未进的「物料编码」节点。"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_fix_prod_card_817762_205.txt"
BIZ = "1.2.817762"

FIX_PY = f'''
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime, timezone
from sqlalchemy import select, text
from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.approver_resolver import ApprovalContext
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_models import (
    WfNodeInstance, WfProcessDefinition, WfProcessInstance,
)
from app.domains.lowcode.workflow_service import (
    _backfill_prod_material_initiator_pending_tasks,
    _published_version,
    _upgrade_drawing_form_flow_if_needed,
)
from app.common.rbac_sync import ensure_prod_material_code_role_members

BIZ = "{BIZ}"


def _node_map(nodes):
    return {{str(n["id"]): n for n in (nodes or []) if isinstance(n, dict) and n.get("id")}}


async def main():
    async with async_session_factory() as db:
        tid = (await db.execute(text("select id from platform_tenants limit 1"))).scalar_one()
        await ensure_prod_material_code_role_members(db, tid)
        await lc.ensure_builtin_form(db, tid, "prod_card_supplement", {{"sub": None}})
        d = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tid,
            WfProcessDefinition.code == "SYS_PROD_CARD_SUPPLEMENT",
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ))).scalar_one()
        await _upgrade_drawing_form_flow_if_needed(db, tid, d, "prod_card_supplement")
        await db.commit()
        ver = await _published_version(db, tid, d.id)
        node_names = {{str(n["id"]): str(n.get("name") or "") for n in (ver.node_definitions or []) if isinstance(n, dict)}}
        material_node_id = next((i for i, n in node_names.items() if n == "物料编码"), None)
        print("FLOW v", ver.version_number, "MATERIAL", material_node_id)

        row = (await db.execute(text("""
            SELECT fi.id, fi.business_no, fi.process_instance_id
            FROM lc_form_instance fi
            WHERE fi.business_no = :biz AND fi.is_deleted = false LIMIT 1
        """), {{"biz": BIZ}})).first()
        if not row:
            print("NOT_FOUND")
            return
        fi_id, bno, pi_id = row
        pi = await db.get(WfProcessInstance, str(pi_id))
        if not pi or pi.status != "running":
            print("PI_STATUS", getattr(pi, "status", None))
            return
        fi = await db.get(FormInstance, str(fi_id))
        ninst = list((await db.execute(
            select(WfNodeInstance).where(WfNodeInstance.process_instance_id == pi.id)
            .order_by(WfNodeInstance.created_at)
        )).scalars().all())

        design_done = any(ni.node_name == "安排设计1" and ni.status in ("completed", "skipped") for ni in ninst)
        material_any = any(ni.node_name == "物料编码" for ni in ninst)
        material_open = any(ni.node_name == "物料编码" and ni.status in ("running", "pending") for ni in ninst)
        print("design_done", design_done, "material_any", material_any, "material_open", material_open)
        if not design_done:
            print("SKIP design1_not_done")
            return

        now = datetime.now(timezone.utc)
        for ni in ninst:
            if ni.node_def_id == "jdy_import_current" and ni.status == "running":
                ni.status = "skipped"
                ni.completed_at = now
                print("SKIP_JDY_PLACEHOLDER", ni.node_name)

        if material_open:
            print("SKIP material_already_open")
        elif not material_any:
            if pi.process_version_id != ver.id:
                print("REBIND", pi.process_version_id, "->", ver.id)
                pi.process_version_id = ver.id
            node_def = _node_map(ver.node_definitions).get(material_node_id or "")
            if not node_def:
                print("NO_MATERIAL_NODE_DEF")
                return
            ctx = ApprovalContext(
                initiator_id=pi.initiator_id or "",
                form_data=dict(fi.form_data or {{}}) if fi else {{}},
                nominated=dict(pi.nominated_approvers or {{}}) or {{}},
            )
            print("ACTIVATE_MATERIAL", node_def.get("name"))
            eng = WorkflowEngine(db, tid)
            await eng._activate_node(pi, ver, node_def, ctx)

        await _backfill_prod_material_initiator_pending_tasks(db, tid)
        await db.commit()

        pending = (await db.execute(text("""
            SELECT u.real_name, u.phone, ni.node_name, t.status
            FROM wf_task_instance t
            JOIN wf_node_instance ni ON ni.id = t.node_instance_id
            JOIN wf_process_instance pi ON pi.id = t.process_instance_id
            JOIN lc_form_instance fi ON fi.id = pi.form_instance_id
            LEFT JOIN users u ON u.id = t.assignee_id
            WHERE fi.business_no = :biz
              AND t.status IN ('pending', 'waiting', 'claimed')
            ORDER BY ni.node_name, u.real_name
        """), {{"biz": BIZ}})).mappings().all()
        print("PENDING", [dict(x) for x in pending])

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
        print(text, flush=True)
        if code != 0:
            OUT.write_text("\n".join(log), encoding="utf-8")
            raise SystemExit(code)
        return text

    with sftp.file("/tmp/_fix_prod_card_817762.py", "w") as f:
        f.write(FIX_PY)
    sftp.close()

    run(
        f"echo {PWD} | sudo -S docker cp /tmp/_fix_prod_card_817762.py "
        f"spt-crm-backend-1:/tmp/_fix_prod_card_817762.py",
    )
    run(
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_fix_prod_card_817762.py",
        timeout=300,
    )
    OUT.write_text("\n".join(log), encoding="utf-8")
    print("wrote", OUT)
    c.close()


if __name__ == "__main__":
    main()
