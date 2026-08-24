#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""205：热补丁物流审批角色 + 挂五人 + 发货通知流程节点改角色审批。"""
from __future__ import annotations

import time
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"
SUDO = f"echo {PWD} | sudo -S"
ROOT = Path(r"G:\ruolin-a\spt-crm")

FILES = [
    ("backend/app/common/rbac_catalog.py", "/app/app/common/rbac_catalog.py"),
    ("backend/app/common/rbac_sync.py", "/app/app/common/rbac_sync.py"),
    ("backend/app/domains/lowcode/workflow_service.py", "/app/app/domains/lowcode/workflow_service.py"),
    ("backend/app/domains/lowcode/service.py", "/app/app/domains/lowcode/service.py"),
    ("backend/app/domains/lowcode/pickable_scope.py", "/app/app/domains/lowcode/pickable_scope.py"),
    ("backend/app/domains/lowcode/shipment_notice_fields.py", "/app/app/domains/lowcode/shipment_notice_fields.py"),
]

INNER = r'''
import asyncio, copy, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

async def main():
    import app.domains.organization.models  # noqa: F401
    from sqlalchemy import select
    from app.common.rbac_sync import ensure_logistics_approval_role_members, ensure_nine_flow_role_members
    from app.database import async_session_factory
    from app.domains.auth.models import Role, User, UserRole
    from app.domains.lowcode.workflow_models import WfProcessDefinition
    from app.domains.lowcode.workflow_service import (
        DRAWING_FORM_FLOW_DESC,
        _publish_system_default_upgrade,
        _published_version,
        apply_shipment_notice_approvers,
        _flow_shipment_logistics_needs_fix,
    )

    tid = "00000000-0000-0000-0000-000000000001"
    async with async_session_factory() as db:
        nine = await ensure_nine_flow_role_members(db, tid)
        await db.commit()
        print("NINE", json.dumps(nine, ensure_ascii=False, default=str))

        logi = await ensure_logistics_approval_role_members(db, tid)
        await db.commit()
        print("LOGI", json.dumps(logi, ensure_ascii=False, default=str))

        role = (await db.execute(
            select(Role).where(Role.tenant_id == tid, Role.code == "logistics_approval")
        )).scalar_one_or_none()
        if not role:
            print("ROLE_MISSING logistics_approval")
            return
        print("ROLE", role.code, role.name, "scope", role.data_scope,
              "sbr", role.scope_by_resource)
        rows = (await db.execute(
            select(User.username, User.real_name).join(
                UserRole, UserRole.user_id == User.id
            ).where(
                UserRole.tenant_id == tid,
                UserRole.role_id == role.id,
            ).order_by(User.real_name)
        )).all()
        print("MEMBERS", [
            {"username": r[0], "name": r[1]} for r in rows
        ])

        d = (await db.execute(
            select(WfProcessDefinition).where(
                WfProcessDefinition.tenant_id == tid,
                WfProcessDefinition.code == "SYS_SHIPMENT_NOTICE",
                WfProcessDefinition.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not d:
            print("NO_DEF SYS_SHIPMENT_NOTICE")
            return
        ver = await _published_version(db, tid, d.id)
        if not ver:
            print("NO_PUB")
            return
        needs = _flow_shipment_logistics_needs_fix(ver.node_definitions)
        print("needs", needs, "ver", ver.version_number)
        for n in ver.node_definitions or []:
            if isinstance(n, dict) and n.get("name") == "物流审批":
                print("BEFORE", n.get("approver_rule"), "multi", n.get("multi_mode"))
        if needs:
            patched = copy.deepcopy(ver.node_definitions or [])
            changed = apply_shipment_notice_approvers(patched)
            print("APPLY changed", changed)
            if changed:
                await _publish_system_default_upgrade(
                    db, tid, d, ver, patched, ver.route_definitions,
                    DRAWING_FORM_FLOW_DESC, "发货通知物流审批改角色 logistics_approval",
                )
                await db.commit()
                ver2 = await _published_version(db, tid, d.id)
                for n in (ver2.node_definitions if ver2 else []) or []:
                    if isinstance(n, dict) and n.get("name") == "物流审批":
                        print("AFTER", n.get("approver_rule"), "multi", n.get("multi_mode"))
                print("UPGRADED", getattr(ver2, "version_number", None))
        else:
            for n in ver.node_definitions or []:
                if isinstance(n, dict) and n.get("name") == "物流审批":
                    print("ALREADY_OK", n.get("approver_rule"))

asyncio.run(main())
print("DONE")
'''


def ssh(c, cmd, timeout=180):
    print(">>", cmd[:160], flush=True)
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[-6000:], flush=True)
    if err.strip():
        print("ERR", err[-800:], flush=True)
    print("exit", code, flush=True)
    if code != 0:
        raise SystemExit(code)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    for local, _ in FILES:
        remote_tmp = f"/tmp/{Path(local).name}"
        sftp.put(str(ROOT / local), remote_tmp)
        print("put", local, "->", remote_tmp)
    with sftp.file("/tmp/_ensure_logistics_205.py", "w") as f:
        f.write(INNER)
    sftp.close()

    ctrs = ("spt-crm-backend-1", "spt-crm-worker-1", "spt-crm-reminder-1")
    for local, dest in FILES:
        tmp = f"/tmp/{Path(local).name}"
        for ctr in ctrs:
            ssh(c, f"{SUDO} docker cp {tmp} {ctr}:{dest}")
    ssh(c, f"{SUDO} docker restart spt-crm-backend-1 spt-crm-worker-1 spt-crm-reminder-1", timeout=180)
    time.sleep(12)
    ssh(c, f"{SUDO} docker cp /tmp/_ensure_logistics_205.py spt-crm-backend-1:/tmp/_ensure_logistics_205.py")
    ssh(c, f"{SUDO} docker exec -e PYTHONPATH=/app spt-crm-backend-1 python /tmp/_ensure_logistics_205.py", timeout=180)
    c.close()
    print("HOTPATCH DONE")


if __name__ == "__main__":
    main()
