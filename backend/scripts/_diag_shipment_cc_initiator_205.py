#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205: 诊断发货通知 24.1-202609050003 抄送发起人问题。"""
from __future__ import annotations

import json
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SERIAL = "202609050003"
BUSINESS_NO = f"24.1-{SERIAL}"

REMOTE = rf'''
import asyncio, json
from sqlalchemy import text
from app.database import async_session_factory

SERIAL = "{SERIAL}"
BUSINESS_NO = "{BUSINESS_NO}"

async def main():
    async with async_session_factory() as db:
        fi = (await db.execute(text("""
            SELECT fi.id::text, fi.business_no, fi.title, fi.status, fi.initiator_id::text,
                   u.real_name AS initiator_name, fi.form_data, fi.process_instance_id::text
            FROM lc_form_instance fi
            LEFT JOIN users u ON u.id = fi.initiator_id
            JOIN lc_form_template t ON t.id = fi.template_id
            WHERE t.code = 'shipment_notice'
              AND (fi.business_no = :bn OR fi.form_data->>'serial_no' = :bn
                   OR fi.business_no LIKE :like OR fi.title LIKE :like)
            ORDER BY fi.created_at DESC
            LIMIT 3
        """), {{"bn": BUSINESS_NO, "like": f"%{{SERIAL}}%"}})).mappings().all()
        print("=== 表单实例 ===")
        for row in fi:
            d = dict(row)
            fd = d.pop("form_data") or {{}}
            d["ship_type"] = fd.get("ship_type")
            d["ship_status"] = fd.get("ship_status")
            d["contract_no"] = fd.get("contract_no") or fd.get("contract_no_select")
            print(json.dumps(d, ensure_ascii=False, indent=2))

        if not fi:
            return
        fi0 = fi[0]
        inst_id = fi0["process_instance_id"]
        fd_full = (await db.execute(text("""
            SELECT form_data FROM lc_form_instance WHERE id = :id
        """), {{"id": fi0["id"]}})).scalar() or {{}}
        print("\n=== 关键表单字段 ===")
        for k in ("ship_status", "ship_type", "is_sales_outbound", "sales_person", "department"):
            print(k, "=", fd_full.get(k))

        if not inst_id:
            print("NO_PROCESS")
            return

        logs = (await db.execute(text("""
            SELECT actor_name, action, opinion, created_at
            FROM wf_task_action_log
            WHERE process_instance_id = :pid
            ORDER BY created_at
        """), {{"pid": inst_id}})).mappings().all()
        print("\n=== 审批动作日志 ===")
        for lg in logs:
            print(dict(lg))

        inst = (await db.execute(text("""
            SELECT id::text, status, initiator_id::text, process_version_id::text, biz_id::text
            FROM wf_process_instance WHERE id = :id
        """), {{"id": inst_id}})).mappings().first()
        print("\n=== 流程实例 ===")
        print(dict(inst) if inst else None)

        nodes = (await db.execute(text("""
            SELECT ni.id::text, ni.node_name, ni.node_type, ni.status, ni.started_at, ni.completed_at,
                   ni.config
            FROM wf_node_instance ni
            WHERE ni.process_instance_id = :pid
            ORDER BY ni.started_at NULLS LAST, ni.completed_at NULLS LAST
        """), {{"pid": inst_id}})).mappings().all()
        print("\n=== 节点轨迹 ===")
        for n in nodes:
            row = dict(n)
            cfg = row.pop("config") or {{}}
            if cfg:
                row["config_keys"] = list(cfg.keys())[:8]
                if cfg.get("skipped"):
                    row["skipped"] = cfg.get("skipped")
                if cfg.get("auto_approve"):
                    row["auto_approve"] = True
            print(json.dumps(row, ensure_ascii=False, default=str))

        ccs = (await db.execute(text("""
            SELECT cc.id::text, cc.user_id::text, u.real_name, cc.is_read, cc.created_at,
                   ni.node_name
            FROM wf_process_cc cc
            JOIN users u ON u.id = cc.user_id
            LEFT JOIN wf_node_instance ni ON ni.id = cc.node_instance_id
            WHERE cc.process_instance_id = :pid
            ORDER BY cc.created_at
        """), {{"pid": inst_id}})).mappings().all()
        print("\n=== 抄送记录 ===")
        for c in ccs:
            print(dict(c))

        tasks = (await db.execute(text("""
            SELECT t.id::text, t.status, t.assignee_id::text, u.real_name AS assignee,
                   ni.node_name, t.created_at, t.completed_at
            FROM wf_task t
            LEFT JOIN users u ON u.id = t.assignee_id
            LEFT JOIN wf_node_instance ni ON ni.id = t.node_instance_id
            WHERE t.process_instance_id = :pid
            ORDER BY t.created_at
        """), {{"pid": inst_id}})).mappings().all()
        print("\n=== 待办任务 ===")
        for t in tasks:
            print(dict(t))

        notifs = (await db.execute(text("""
            SELECT n.id::text, n.type, n.title, n.recipient_id::text, u.real_name,
                   n.created_at, n.is_read
            FROM notifications n
            LEFT JOIN users u ON u.id = n.recipient_id
            WHERE n.link LIKE :lk OR n.content LIKE :lk2
            ORDER BY n.created_at DESC
            LIMIT 20
        """), {{"lk": f"%{{inst_id}}%", "lk2": f"%{{SERIAL}}%"}})).mappings().all()
        print("\n=== 相关通知(近20) ===")
        for n in notifs:
            print(dict(n))

        ver_id = inst["process_version_id"] if inst else None
        if ver_id:
            ver = (await db.execute(text("""
                SELECT node_definitions, route_definitions
                FROM wf_process_version WHERE id = :id
            """), {{"id": ver_id}})).mappings().first()
            if ver:
                nd = ver["node_definitions"] or []
                cc_nodes = [{{"id": n.get("id"), "name": n.get("name"), "type": n.get("type"),
                             "approver_rule": n.get("approver_rule")}}
                            for n in nd if isinstance(n, dict) and n.get("type") == "cc"
                            and ("发起人" in (n.get("name") or "") or "业务员" in (n.get("name") or ""))]
                print("\n=== 流程定义-相关抄送节点 ===")
                print(json.dumps(cc_nodes, ensure_ascii=False, indent=2))

asyncio.run(main())
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
sftp = c.open_sftp()
with sftp.file("/tmp/_diag_ship_notice_cc.py", "w") as f:
    f.write(REMOTE)
sftp.close()
_, o, e = c.exec_command(
    f"echo {PWD} | sudo -S bash -lc "
    "'cat /tmp/_diag_ship_notice_cc.py | docker exec -i spt-crm-backend-1 python -'",
    timeout=120,
)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR:", err[-2000:])
c.close()
