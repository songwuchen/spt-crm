#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地：创建物流审批角色、挂五人、升级发货通知流程节点。"""
from __future__ import annotations

import asyncio
import copy
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    import app.domains.organization.models  # noqa: F401
    from sqlalchemy import select, text

    from app.common.rbac_sync import (
        ensure_logistics_approval_role_members,
        ensure_nine_flow_role_members,
    )
    from app.database import async_session_factory
    from app.domains.auth.models import Role, User, UserRole
    from app.domains.lowcode.workflow_models import WfProcessDefinition
    from app.domains.lowcode.workflow_service import (
        DRAWING_FORM_FLOW_DESC,
        _flow_shipment_logistics_needs_fix,
        _publish_system_default_upgrade,
        _published_version,
        apply_shipment_notice_approvers,
    )

    tid = "00000000-0000-0000-0000-000000000001"
    async with async_session_factory() as db:
        try:
            t = (await db.execute(text("SELECT id FROM platform_tenants LIMIT 1"))).scalar()
            if t:
                tid = str(t)
        except Exception:
            await db.rollback()

        print("tenant", tid)
        nine = await ensure_nine_flow_role_members(db, tid)
        await db.commit()
        print("NINE logistics", json.dumps(nine.get("logistics_approval"), ensure_ascii=False, default=str))

        logi = await ensure_logistics_approval_role_members(db, tid)
        await db.commit()
        print("LOGI", json.dumps(logi, ensure_ascii=False, default=str))

        role = (
            await db.execute(
                select(Role).where(Role.tenant_id == tid, Role.code == "logistics_approval")
            )
        ).scalar_one_or_none()
        print("ROLE", None if not role else (role.name, role.scope_by_resource))
        if role:
            rows = (
                await db.execute(
                    select(User.real_name, User.username)
                    .join(UserRole, UserRole.user_id == User.id)
                    .where(UserRole.role_id == role.id)
                    .order_by(User.real_name)
                )
            ).all()
            print("MEMBERS", [(r[0], r[1]) for r in rows])

        d = (
            await db.execute(
                select(WfProcessDefinition).where(
                    WfProcessDefinition.tenant_id == tid,
                    WfProcessDefinition.code == "SYS_SHIPMENT_NOTICE",
                    WfProcessDefinition.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if not d:
            d = (
                await db.execute(
                    select(WfProcessDefinition).where(
                        WfProcessDefinition.tenant_id == tid,
                        WfProcessDefinition.form_code == "shipment_notice",
                        WfProcessDefinition.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalars().first()
        if not d:
            print("NO_DEF")
            return

        ver = await _published_version(db, tid, d.id)
        print("VER", getattr(ver, "version_number", None), "def", d.code)
        needs = _flow_shipment_logistics_needs_fix(ver.node_definitions if ver else None)
        print("needs", needs)
        for n in (ver.node_definitions if ver else []) or []:
            if isinstance(n, dict) and n.get("name") == "物流审批":
                print("BEFORE", n.get("approver_rule"))

        if needs and ver:
            patched = copy.deepcopy(ver.node_definitions or [])
            changed = apply_shipment_notice_approvers(patched)
            print("APPLY", changed)
            if changed:
                await _publish_system_default_upgrade(
                    db,
                    tid,
                    d,
                    ver,
                    patched,
                    ver.route_definitions,
                    DRAWING_FORM_FLOW_DESC,
                    "本地：发货通知物流审批改角色 logistics_approval",
                )
                await db.commit()
                ver2 = await _published_version(db, tid, d.id)
                for n in (ver2.node_definitions if ver2 else []) or []:
                    if isinstance(n, dict) and n.get("name") == "物流审批":
                        print("AFTER", n.get("approver_rule"), "multi", n.get("multi_mode"))
                print("UPGRADED", getattr(ver2, "version_number", None))


if __name__ == "__main__":
    asyncio.run(main())
