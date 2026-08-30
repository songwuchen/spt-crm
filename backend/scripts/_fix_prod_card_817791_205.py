#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 补开 1.2.817791「安排设计1」后未进的「物料编码」节点。"""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_fix_prod_card_817791_205.txt"
BIZ = "1.2.817791"

FIX_PY = f'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select, text
from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.approver_resolver import ApprovalContext
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.workflow_engine import WorkflowEngine
from app.domains.lowcode.workflow_models import (
    WfNodeInstance, WfProcessDefinition, WfProcessInstance, WfTaskInstance,
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


def _names(nodes):
    return {{str(n["id"]): str(n.get("name") or "") for n in (nodes or []) if isinstance(n, dict)}}


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
        print("FLOW v", ver.version_number)
        node_names = _names(ver.node_definitions)
        design_ids = {{i for i, n in node_names.items() if n == "安排设计1"}}
        material_ids = {{i for i, n in node_names.items() if n == "物料编码"}}
        material_node_id = next(iter(material_ids), None)
        print("DESIGN1_IDS", design_ids, "MATERIAL_IDS", material_ids)

        row = (await db.execute(text("""
            SELECT fi.id, fi.business_no, fi.status, fi.process_instance_id
            FROM lc_form_instance fi
            WHERE fi.business_no = :biz AND fi.is_deleted = false
            LIMIT 1
        """), {{"biz": BIZ}})).first()
        if not row:
            print("NOT_FOUND", BIZ)
            return
        fi_id, bno, fi_status, pi_id = row
        print("INSTANCE", bno, "fi_status", fi_status, "pi_id", pi_id)
        if not pi_id:
            print("NO_PROCESS")
            return

        pi = await db.get(WfProcessInstance, str(pi_id))
        if not pi or pi.status != "running":
            print("PI_STATUS", getattr(pi, "status", None))
            return

        fi = await db.get(FormInstance, str(fi_id))
        ninst = list((await db.execute(
            select(WfNodeInstance).where(WfNodeInstance.process_instance_id == pi.id)
            .order_by(WfNodeInstance.created_at)
        )).scalars().all())
        design_done = any(
            ni.node_name == "安排设计1" and ni.status in ("completed", "skipped")
            for ni in ninst
        )
        material_any = any(ni.node_name == "物料编码" for ni in ninst)
        material_open = any(
            ni.node_name == "物料编码" and ni.status in ("running", "pending")
            for ni in ninst
        )
        print("design_done", design_done, "material_any", material_any, "material_open", material_open)
        if not design_done:
            print("SKIP design1_not_done")
            return
        if material_open:
            print("SKIP material_already_open")
        elif material_any and not material_open:
            print("material_done_reactivate?")
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
            print("ACTIVATE_MATERIAL", node_def.get("name"), node_def.get("id"))
            eng = WorkflowEngine(db, tid)
            await eng._activate_node(pi, ver, node_def, ctx)
            await db.commit()

        n_bf = await _backfill_prod_material_initiator_pending_tasks(db, tid)
        await db.commit()
        print("BACKFILL_INITIATOR", n_bf)

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

    with sftp.file("/tmp/_fix_prod_card_817791.py", "w") as f:
        f.write(FIX_PY)
    sftp.close()

    run(
        f"echo {PWD} | sudo -S docker cp /tmp/_fix_prod_card_817791.py "
        f"spt-crm-backend-1:/tmp/_fix_prod_card_817791.py",
    )
    run(
        f"echo {PWD} | sudo -S docker exec -e PYTHONPATH=/app -w /app spt-crm-backend-1 "
        f"python /tmp/_fix_prod_card_817791.py",
        timeout=300,
    )
    OUT.write_text("\n".join(log), encoding="utf-8")
    print("wrote", OUT)
    c.close()


if __name__ == "__main__":
    main()
