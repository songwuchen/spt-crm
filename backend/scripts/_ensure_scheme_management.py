"""Ensure scheme_management builtin fields are synced for every template copy."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session_factory
from app.domains.lowcode import service as lc
from app.domains.lowcode.models import FormTemplate, FormTemplateVersion


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
            by_id = {f.get("id"): f for f in (pub.field_definitions or []) if isinstance(f, dict)}
            ac = by_id.get("apply_or_change") or {}
            vis = [
                r.get("id") for r in (pub.rule_definitions or [])
                if r.get("target_field_id") == "apply_or_change"
                or "apply_or_change" in (r.get("target_field_ids") or [])
            ]
            print(
                f"tenant={tpl.tenant_id[:8]} tpl={out.id[:8]} ver={pub.version_number} "
                f"apply_or_change={ac.get('type')!r}/{ac.get('label')!r} vis={vis}"
            )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
