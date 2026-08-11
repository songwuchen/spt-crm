# -*- coding: utf-8 -*-
"""Smoke: ensure 6 个客户服务部 builtin + SYS_CS_* 流程。"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text

from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.models import FormTemplateVersion
from app.domains.lowcode.workflow_models import WfProcessDefinition, WfProcessDefinitionVersion
from app.domains.lowcode.workflow_service import _flow_is_jdy_customer_service

CHECKS = (
    ("cs_service_request", "SYS_CS_SERVICE_REQUEST"),
    ("cs_product_replace", "SYS_CS_PRODUCT_REPLACE"),
    ("cs_product_return", "SYS_CS_PRODUCT_RETURN"),
    ("cs_loan_slip", "SYS_CS_LOAN_SLIP"),
    ("cs_service_delay", "SYS_CS_SERVICE_DELAY"),
    ("cs_correspondence", "SYS_CS_CORRESPONDENCE"),
)


async def main():
    async with async_session_factory() as db:
        tenant = (await db.execute(text("select id from platform_tenants limit 1"))).scalar_one()
        user = {"sub": None}
        ok = True
        for key, code in CHECKS:
            tpl = await lc.ensure_builtin_form(db, tenant, key, user)
            pub = (await db.execute(select(FormTemplateVersion).where(
                FormTemplateVersion.template_id == tpl.id,
                FormTemplateVersion.status == "published",
            ).order_by(FormTemplateVersion.version_number.desc()).limit(1))).scalar_one()
            ids = [f.get("id") for f in (pub.field_definitions or [])]
            print(f"{key}: tpl={tpl.id[:8]} ver={pub.version_number} fields={len(ids)} sample={ids[:6]}")

            d = (await db.execute(select(WfProcessDefinition).where(
                WfProcessDefinition.tenant_id == tenant,
                WfProcessDefinition.form_template_id == tpl.id,
                WfProcessDefinition.is_deleted == False,  # noqa: E712
            ).limit(1))).scalar_one_or_none()
            if not d:
                print("  FLOW MISSING")
                ok = False
                continue
            v = (await db.execute(select(WfProcessDefinitionVersion).where(
                WfProcessDefinitionVersion.process_definition_id == d.id,
                WfProcessDefinitionVersion.status == "published",
            ).order_by(WfProcessDefinitionVersion.version_number.desc()).limit(1))).scalar_one()
            jdy = _flow_is_jdy_customer_service(v.node_definitions)
            n = len(v.node_definitions or [])
            print(
                f"  flow={d.code} expect={code} name={d.name} ver={v.version_number} "
                f"jdy={jdy} nodes={n}"
            )
            if d.code != code or not jdy:
                ok = False
                print("  FAIL code/jdy mismatch")
        await db.commit()
        # 确认原生售后工单表仍存在、未因 ensure 被污染（仅检查表可查）
        n_tickets = (await db.execute(text("select count(*) from service_tickets"))).scalar_one()
        print(f"service_tickets count={n_tickets} (untouched by CS ensure)")
        if not ok:
            sys.exit(1)
        print("ENSURE_OK")


if __name__ == "__main__":
    asyncio.run(main())
