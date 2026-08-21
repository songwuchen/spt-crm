# -*- coding: utf-8 -*-
"""本地：创建九流程业务角色、挂成员，并对目标 form 强制 apply 升级发布流。"""
from __future__ import annotations

import asyncio
import copy
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    import app.domains.organization.models  # noqa: F401
    from sqlalchemy import select, text

    from app.common.rbac_sync import ensure_nine_flow_role_members, BUSINESS_ROLE_CODES
    from app.database import async_session_factory
    from app.domains.auth.models import Role
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

    forms = {
        "shipment_notice": (apply_shipment_notice_approvers, _flow_shipment_logistics_needs_fix),
        "cs_product_replace": (apply_cs_product_replace_approvers, _flow_cs_product_replace_needs_approver_fix),
        "cs_product_return": (apply_cs_product_return_approvers, _flow_cs_product_return_needs_approver_fix),
        "cs_service_delay": (apply_cs_service_delay_approvers, _flow_cs_service_delay_needs_approver_fix),
        "cs_correspondence": (apply_cs_correspondence_approvers, _flow_cs_correspondence_needs_approver_fix),
        "xunhan_contract_review": (apply_xunhan_contract_review_approvers, _flow_xunhan_contract_review_needs_approver_fix),
        "prod_card_supplement": (apply_prod_card_supplement_approvers, _flow_prod_card_supplement_needs_approver_fix),
    }

    async with async_session_factory() as db:
        tid = (await db.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()
        print("tenant", tid)
        if not tid:
            return
        res = await ensure_nine_flow_role_members(db, tid)
        await db.commit()
        print("ENSURE", json.dumps(res, ensure_ascii=False, default=str))

        roles = (
            await db.execute(
                select(Role).where(Role.tenant_id == tid, Role.code.in_(list(BUSINESS_ROLE_CODES)))
            )
        ).scalars().all()
        print("ROLES", sorted((r.code, r.name) for r in roles))

        for form_code, (apply_fn, needs_fn) in forms.items():
            d = (
                await db.execute(
                    select(WfProcessDefinition).where(
                        WfProcessDefinition.tenant_id == tid,
                        WfProcessDefinition.form_code == form_code,
                        WfProcessDefinition.is_active == True,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            if not d:
                print("SKIP_NO_DEF", form_code)
                continue
            version = await _published_version(db, d.id)
            if not version:
                print("SKIP_NO_PUB", form_code)
                continue
            needs = needs_fn(version.node_definitions)
            print("CHECK", form_code, "needs", needs)
            if not needs:
                continue
            patched = copy.deepcopy(version.node_definitions or [])
            changed = apply_fn(patched)
            print("APPLY", form_code, "changed", changed)
            if not changed:
                continue
            await _publish_system_default_upgrade(
                db,
                tid,
                d,
                version,
                patched,
                version.route_definitions,
                DRAWING_FORM_FLOW_DESC,
                f"九流程角色对齐本地冒烟({form_code})",
            )
            await db.commit()
            print("UPGRADED", form_code)


if __name__ == "__main__":
    asyncio.run(main())
