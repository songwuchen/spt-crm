"""强制把本地 SYS_CS_SERVICE_REQUEST 客服落实改成指定角色 cs_office。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    import app.domains.organization.models  # noqa: F401
    from sqlalchemy import select

    from app.common.rbac_sync import ensure_cs_office_role_members
    from app.database import async_session_factory
    from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
    from app.domains.lowcode.workflow_service import (
        DRAWING_FORM_FLOW_DESC,
        _flow_cs_service_request_needs_approver_fix,
        _publish_system_default_upgrade,
        _published_version,
        apply_cs_service_request_approvers,
    )

    tenant_id = "00000000-0000-0000-0000-000000000001"
    async with async_session_factory() as db:
        info = await ensure_cs_office_role_members(db, tenant_id)
        await db.commit()
        print("role_members", info)

        d = (
            await db.execute(
                select(WfProcessDefinition).where(
                    WfProcessDefinition.tenant_id == tenant_id,
                    WfProcessDefinition.code == "SYS_CS_SERVICE_REQUEST",
                )
            )
        ).scalar_one_or_none()
        if not d:
            print("no definition")
            return
        ver = await _published_version(db, tenant_id, d.id)
        if not ver:
            print("no published version")
            return
        print("before needs", _flow_cs_service_request_needs_approver_fix(ver.node_definitions))
        for n in ver.node_definitions or []:
            if n.get("id") == "n2" or n.get("name") == "客服落实":
                print("before", n.get("approver_rule"))

        import copy
        patched = copy.deepcopy(ver.node_definitions or [])
        changed = apply_cs_service_request_approvers(patched)
        print("apply changed", changed)
        if changed:
            await _publish_system_default_upgrade(
                db, tenant_id, d, ver,
                patched, ver.route_definitions,
                DRAWING_FORM_FLOW_DESC, "客服落实改为指定角色cs_office(force)",
            )
            await db.commit()

        ver2 = await _published_version(db, tenant_id, d.id)
        for n in (ver2.node_definitions or []) if ver2 else []:
            if n.get("id") == "n2" or n.get("name") == "客服落实":
                print("after", n.get("approver_rule"), "ver", ver2.version_number)


if __name__ == "__main__":
    asyncio.run(main())
