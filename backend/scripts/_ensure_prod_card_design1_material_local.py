#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地：补回安排设计1→物料编码边；清理重复 published 版本。"""
from __future__ import annotations

import asyncio
import copy
import json
import sys

from sqlalchemy import select, text, update

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from app.database import async_session_factory
from app.domains.lowcode.workflow_models import (
    WfProcessDefinition,
    WfProcessDefinitionVersion,
)
from app.domains.lowcode.workflow_service import (
    DRAWING_FORM_FLOW_DESC,
    _flow_missing_prod_card_design1_material_route,
    _publish_system_default_upgrade,
    _published_version,
    fix_packaging_fork_serial_priority,
    _prod_card_routes_ready_for_publish,
)


async def main() -> None:
    async with async_session_factory() as db:
        tid = (await db.execute(text("select id from platform_tenants limit 1"))).scalar_one()
        d = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tid,
            WfProcessDefinition.code == "SYS_PROD_CARD_SUPPLEMENT",
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ))).scalar_one()
        ver0 = await _published_version(db, tid, d.id)
        print("BEFORE v", ver0.version_number, "missing_route",
              _flow_missing_prod_card_design1_material_route(
                  ver0.node_definitions, ver0.route_definitions))

        # 历史脏数据：多条 status=published，只保留最新号
        pub_rows = (await db.execute(select(WfProcessDefinitionVersion).where(
            WfProcessDefinitionVersion.process_definition_id == d.id,
            WfProcessDefinitionVersion.status == "published",
        ).order_by(WfProcessDefinitionVersion.version_number))).scalars().all()
        if len(pub_rows) > 1:
            keep = pub_rows[-1]
            stale = [v for v in pub_rows[:-1] if v.id != keep.id]
            for v in stale:
                v.status = "deprecated"
            print("DEPRECATED stale published", [v.version_number for v in stale])
            await db.flush()

        if _flow_missing_prod_card_design1_material_route(
            ver0.node_definitions, ver0.route_definitions,
        ):
            patched_routes = copy.deepcopy(ver0.route_definitions or [])
            _prod_card_routes_ready_for_publish(ver0.node_definitions, patched_routes)
            fix_packaging_fork_serial_priority(ver0.node_definitions, patched_routes)
            await _publish_system_default_upgrade(
                db, tid, d, ver0,
                ver0.node_definitions, patched_routes,
                d.description or DRAWING_FORM_FLOW_DESC,
                "补回安排设计1→物料编码(transfer_packaging为空)",
            )

        ver = await _published_version(db, tid, d.id)
        print("AFTER v", ver.version_number, "missing_route",
              _flow_missing_prod_card_design1_material_route(
                  ver.node_definitions, ver.route_definitions))
        design_ids = [
            n["id"] for n in (ver.node_definitions or [])
            if isinstance(n, dict) and n.get("name") == "安排设计1"
        ]
        mat_ids = [
            n["id"] for n in (ver.node_definitions or [])
            if isinstance(n, dict) and n.get("name") == "物料编码"
        ]
        for r in ver.route_definitions or []:
            if isinstance(r, dict) and str(r.get("source")) in design_ids and str(r.get("target")) in mat_ids:
                print("ROUTE", json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
