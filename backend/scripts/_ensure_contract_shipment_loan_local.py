# -*- coding: utf-8 -*-
"""本地/Docker：注册并发布 contract_shipment_loan 内置表单 + 默认流程。"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text

from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.models import FormTemplateVersion
from app.domains.lowcode.workflow_models import WfProcessDefinition


async def main() -> None:
    async with async_session_factory() as db:
        tenant = (await db.execute(text("select id from platform_tenants limit 1"))).scalar_one()
        user = {"sub": None}
        tpl = await lc.ensure_builtin_form(db, tenant, "contract_shipment_loan", user)
        pub = (await db.execute(
            select(FormTemplateVersion).where(
                FormTemplateVersion.template_id == tpl.id,
                FormTemplateVersion.status == "published",
            ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
        )).scalar_one()
        wf = (await db.execute(
            select(WfProcessDefinition).where(
                WfProcessDefinition.tenant_id == tenant,
                WfProcessDefinition.code == "SYS_CONTRACT_SHIPMENT_LOAN",
                WfProcessDefinition.is_deleted == False,  # noqa: E712
            ).limit(1)
        )).scalar_one_or_none()
        n_fields = len(pub.field_definitions or [])
        n_nodes = 0
        if wf:
            from app.domains.lowcode.workflow_service import _published_version
            ver = await _published_version(db, tenant, wf.id)
            if ver:
                n_nodes = len(ver.node_definitions or [])
        print(
            f"OK contract_shipment_loan tpl={tpl.id} fields={n_fields} "
            f"wf={'yes' if wf else 'no'} nodes={n_nodes}"
        )


if __name__ == "__main__":
    asyncio.run(main())
