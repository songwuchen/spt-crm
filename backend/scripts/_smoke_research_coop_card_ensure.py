"""Smoke: ensure_builtin_form for research_coop_card."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
from app.domains.lowcode.models import FormTemplateVersion
from app.domains.lowcode.workflow_service import _flow_is_jdy_form_graph


async def main():
    async with async_session_factory() as db:
        tenant = (await db.execute(text("select id from platform_tenants limit 1"))).scalar_one()
        tpl = await lc.ensure_builtin_form(db, tenant, "research_coop_card", {"sub": None})
        pub = (await db.execute(select(FormTemplateVersion).where(
            FormTemplateVersion.template_id == tpl.id,
            FormTemplateVersion.status == "published",
        ).order_by(FormTemplateVersion.version_number.desc()).limit(1))).scalar_one()
        ids = [f.get("id") for f in (pub.field_definitions or [])]
        print(
            f"tpl={tpl.id[:8]} ver={pub.version_number} "
            f"fields={len(ids)} rules={len(pub.rule_definitions or [])}"
        )
        d = (await db.execute(select(WfProcessDefinition).where(
            WfProcessDefinition.tenant_id == tenant,
            WfProcessDefinition.form_template_id == tpl.id,
            WfProcessDefinition.is_deleted == False,  # noqa: E712
        ).limit(1))).scalar_one_or_none()
        if not d:
            print("FLOW MISSING")
            return
        v = (await db.execute(select(WfProcessDefinitionVersion).where(
            WfProcessDefinitionVersion.process_definition_id == d.id,
            WfProcessDefinitionVersion.status == "published",
        ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one()
        names = [
            n.get("name") for n in (v.node_definitions or [])
            if n.get("type") in ("approval", "cc")
        ]
        jdy = _flow_is_jdy_form_graph("research_coop_card", v.node_definitions)
        print(f"flow={d.code} name={d.name} ver={v.version_number} jdy={jdy} nodes={names}")


if __name__ == "__main__":
    asyncio.run(main())
