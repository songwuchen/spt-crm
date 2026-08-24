# -*- coding: utf-8 -*-
"""205：创建九流程业务角色、挂成员，并强制 apply 升级发布流。"""
from __future__ import annotations

import base64
import json
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = "192.168.1.205"
USER = "swc"
PASSWORD = "Ruolin2025"

PY = r'''
import asyncio, copy, json, sys
sys.stdout.reconfigure(encoding="utf-8")

async def main():
    import app.domains.organization.models  # noqa: F401
    from sqlalchemy import select, text
    from app.common.rbac_sync import ensure_nine_flow_role_members
    from app.database import async_session_factory
    from app.domains.auth.models import Role, User, UserRole
    from app.domains.lowcode.workflow_models import WfProcessDefinition
    from app.domains.lowcode.workflow_service import (
        DRAWING_FORM_FLOW_DESC,
        _publish_system_default_upgrade,
        _published_version,
        apply_shipment_notice_approvers,
        apply_cs_product_replace_approvers,
        apply_cs_product_return_approvers,
        apply_cs_service_delay_approvers,
        apply_cs_correspondence_approvers,
        apply_xunhan_contract_review_approvers,
        apply_prod_card_supplement_approvers,
        _flow_shipment_logistics_needs_fix,
        _flow_cs_product_replace_needs_approver_fix,
        _flow_cs_product_return_needs_approver_fix,
        _flow_cs_service_delay_needs_approver_fix,
        _flow_cs_correspondence_needs_approver_fix,
        _flow_xunhan_contract_review_needs_approver_fix,
        _flow_prod_card_supplement_needs_approver_fix,
    )

    tid = "00000000-0000-0000-0000-000000000001"
    forms = {
        "SYS_SHIPMENT_NOTICE": (apply_shipment_notice_approvers, _flow_shipment_logistics_needs_fix, "shipment_notice"),
        "SYS_CS_PRODUCT_REPLACE": (apply_cs_product_replace_approvers, _flow_cs_product_replace_needs_approver_fix, "cs_product_replace"),
        "SYS_CS_PRODUCT_RETURN": (apply_cs_product_return_approvers, _flow_cs_product_return_needs_approver_fix, "cs_product_return"),
        "SYS_CS_SERVICE_DELAY": (apply_cs_service_delay_approvers, _flow_cs_service_delay_needs_approver_fix, "cs_service_delay"),
        "SYS_CS_CORRESPONDENCE": (apply_cs_correspondence_approvers, _flow_cs_correspondence_needs_approver_fix, "cs_correspondence"),
        "SYS_XUNHAN_CONTRACT_REVIEW": (apply_xunhan_contract_review_approvers, _flow_xunhan_contract_review_needs_approver_fix, "xunhan_contract_review"),
        "SYS_PROD_CARD_SUPPLEMENT": (apply_prod_card_supplement_approvers, _flow_prod_card_supplement_needs_approver_fix, "prod_card_supplement"),
    }

    async with async_session_factory() as db:
        res = await ensure_nine_flow_role_members(db, tid)
        await db.commit()
        print("ENSURE", json.dumps(res, ensure_ascii=False, default=str))

        for code in (
            "cs_office", "cs_delay_approve", "logistics_approval",
            "ship_sales_outbound", "gate_guard", "prod_material_code", "legal",
        ):
            role = (await db.execute(
                select(Role).where(Role.tenant_id == tid, Role.code == code)
            )).scalar_one_or_none()
            if not role:
                print("ROLE_MISSING", code)
                continue
            rows = (await db.execute(
                select(User.username, User.real_name).join(
                    UserRole, UserRole.user_id == User.id
                ).where(
                    UserRole.tenant_id == tid,
                    UserRole.role_id == role.id,
                ).order_by(User.real_name)
            )).all()
            print("MEMBERS", code, len(rows), [
                {"username": r[0], "name": r[1]} for r in rows
            ])

        for def_code, (apply_fn, needs_fn, form_code) in forms.items():
            d = (await db.execute(
                select(WfProcessDefinition).where(
                    WfProcessDefinition.tenant_id == tid,
                    WfProcessDefinition.code == def_code,
                    WfProcessDefinition.is_deleted == False,  # noqa: E712
                )
            )).scalar_one_or_none()
            if not d:
                print("SKIP_NO_DEF", def_code, form_code)
                continue
            ver = await _published_version(db, tid, d.id)
            if not ver:
                print("SKIP_NO_PUB", def_code)
                continue
            needs = needs_fn(ver.node_definitions)
            print("CHECK", form_code, "needs", needs)
            if not needs:
                continue
            patched = copy.deepcopy(ver.node_definitions or [])
            changed = apply_fn(patched)
            print("APPLY", form_code, "changed", changed)
            if not changed:
                continue
            await _publish_system_default_upgrade(
                db, tid, d, ver, patched, ver.route_definitions,
                DRAWING_FORM_FLOW_DESC, f"九流程角色对齐205({form_code})",
            )
            await db.commit()
            print("UPGRADED", form_code)

asyncio.run(main())
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, look_for_keys=False, allow_agent=False)
    b64 = base64.b64encode(PY.encode()).decode()
    cmd = (
        f"echo {PASSWORD} | sudo -S docker exec -i -e PYTHONPATH=/app spt-crm-backend-1 "
        f"sh -c 'echo {b64} | base64 -d > /tmp/_nine_roles.py && python /tmp/_nine_roles.py'"
    )
    _, o, e = c.exec_command(cmd, timeout=180)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR", err[-800:])
    c.close()


if __name__ == "__main__":
    main()
