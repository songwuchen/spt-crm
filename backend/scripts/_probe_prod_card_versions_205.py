#!/usr/bin/env python3
"""205: 对比生产卡流程各版本「安排设计1→物料编码」边是否存在。"""
from __future__ import annotations

import base64
import json
import paramiko

HOST, USER, PWD = "192.168.1.205", "swc", "Ruolin2025"

PY = r'''
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import select
from app.database import async_session_factory
from app.domains.lowcode.models import FormTemplate
from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion

async def main():
    async with async_session_factory() as db:
        tpls = (await db.execute(
            select(FormTemplate).where(FormTemplate.code == "prod_card_supplement")
        )).scalars().all()
        if not tpls:
            print("NO_TEMPLATE")
            return
        for tpl in tpls:
            print("=== TPL", tpl.id, tpl.name, "===")
            defs = (await db.execute(
                select(WfProcessDefinition).where(
                    WfProcessDefinition.form_template_id == tpl.id,
                    WfProcessDefinition.is_deleted == False,  # noqa: E712
                ).order_by(WfProcessDefinition.created_at)
            )).scalars().all()
            if not defs:
                print("NO_DEF")
                continue
            for d in defs:
                print("--- DEF", d.id, d.code, d.name, "---")
                vers = (await db.execute(
                    select(WfProcessDefinitionVersion).where(
                        WfProcessDefinitionVersion.process_definition_id == d.id
                    ).order_by(WfProcessDefinitionVersion.version_number)
                )).scalars().all()
                print("versions", len(vers))
                for v in vers:
                    nodes = {n["id"]: n.get("name") for n in (v.node_definitions or []) if isinstance(n, dict)}
                    design_ids = [i for i,n in nodes.items() if n == "安排设计1"]
                    mat_id = next((i for i,n in nodes.items() if n == "物料编码"), None)
                    outs = []
                    mat_in = []
                    for r in v.route_definitions or []:
                        if str(r.get("source")) in design_ids:
                            outs.append(nodes.get(str(r.get("target")), r.get("target")))
                        if str(r.get("target")) == mat_id:
                            mat_in.append((nodes.get(str(r.get("source"))), r.get("condition")))
                    has_direct = "物料编码" in outs
                    print(
                        "V", v.version_number, v.status,
                        "published", str(v.published_at or "")[:19],
                        "direct_design->material", has_direct,
                        "design_outs", outs,
                        "material_in", [(a, json.dumps(c, ensure_ascii=False)[:60] if c else None) for a,c in mat_in],
                    )

asyncio.run(main())
'''

def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    b64 = base64.b64encode(PY.encode()).decode()
    cmd = (
        f"echo {PWD} | sudo -S docker exec -i -e PYTHONPATH=/app spt-crm-backend-1 "
        f"sh -c 'echo {b64} | base64 -d > /tmp/_prod_card_ver_cmp.py && python /tmp/_prod_card_ver_cmp.py'"
    )
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR", err[-1500:])
    c.close()


if __name__ == "__main__":
    main()
