"""Ensure scheme_management fields + flow (总工 need_gm_approval) for every template."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.models import FormTemplate, FormTemplateVersion
from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
from app.domains.lowcode.biz_score import flow_missing_chief_gm_perm


async def main():
    async with async_session_factory() as db:
        tpls = (await db.execute(
            select(FormTemplate).where(
                FormTemplate.code == "scheme_management",
                FormTemplate.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        user = {"sub": None}
        if not tpls:
            print("no scheme_management templates")
            return
        for tpl in tpls:
            out = await lc.ensure_builtin_form(db, tpl.tenant_id, "scheme_management", user)
            pub = (await db.execute(select(FormTemplateVersion).where(
                FormTemplateVersion.template_id == out.id,
                FormTemplateVersion.status == "published",
            ).order_by(FormTemplateVersion.version_number.desc()).limit(1))).scalar_one()
            gm_vis = [
                r.get("id") for r in (pub.rule_definitions or [])
                if r.get("type") == "visibility"
                and (
                    r.get("target_field_id") == "need_gm_approval"
                    or "need_gm_approval" in (r.get("target_field_ids") or [])
                )
            ]
            f = next((x for x in pub.field_definitions if x.get("id") == "need_gm_approval"), {})
            d = (await db.execute(select(WfProcessDefinition).where(
                WfProcessDefinition.tenant_id == tpl.tenant_id,
                WfProcessDefinition.form_template_id == out.id,
                WfProcessDefinition.is_deleted == False,  # noqa: E712
            ).limit(1))).scalar_one_or_none()
            flow_info = "no-flow"
            if d:
                v = (await db.execute(select(WfProcessDefinitionVersion).where(
                    WfProcessDefinitionVersion.process_definition_id == d.id,
                    WfProcessDefinitionVersion.status == "published",
                ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one()
                chiefs = []
                for n in v.node_definitions or []:
                    if n.get("name") == "总工审批":
                        chiefs.append((n.get("id"), n.get("field_perms")))
                flow_info = f"flow_ver={v.version_number} missing={flow_missing_chief_gm_perm(v.node_definitions)} chiefs={chiefs}"
            print(
                f"tenant={tpl.tenant_id[:8]} tpl={out.id[:8]} form_ver={pub.version_number} "
                f"need_gm={f.get('fill_stage')}/{f.get('available_on_create')} gm_vis={gm_vis} {flow_info}"
            )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
