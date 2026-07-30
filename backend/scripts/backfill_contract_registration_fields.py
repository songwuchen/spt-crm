"""Backfill contract P0 fields from custom_fields_json / migration leftovers.

Usage (from backend/):
    python -m scripts.backfill_contract_registration_fields
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session_factory
from app.domains.contract.models import Contract

logger = logging.getLogger("backfill_contract_reg")
logging.basicConfig(level=logging.INFO)


def _cf_get(cf: dict | None, *keys: str):
    if not cf:
        return None
    for k in keys:
        v = cf.get(k)
        if v not in (None, ""):
            return v
    return None


async def run() -> None:
    updated = 0
    async with async_session_factory() as db:
        rows = (await db.execute(select(Contract))).scalars().all()
        for c in rows:
            cf = c.custom_fields_json or {}
            changed = False
            if not c.drawing_no:
                v = _cf_get(cf, "图纸编号", "drawing_no")
                if v:
                    c.drawing_no = str(v)[:100]
                    changed = True
            if not c.peer_contract_no:
                v = _cf_get(cf, "对方合同号", "peer_contract_no")
                if v:
                    c.peer_contract_no = str(v)[:100]
                    changed = True
            if not c.acquire_method:
                v = _cf_get(cf, "合同获取方式", "获取方式", "acquire_method")
                if v:
                    c.acquire_method = str(v)[:64]
                    changed = True
            if not c.change_type:
                v = _cf_get(cf, "合同状态", "登记类型", "change_type")
                if v:
                    s = str(v)
                    c.change_type = "change" if "变动" in s else ("new" if "新增" in s else s[:16])
                    changed = True
            if changed:
                updated += 1
        await db.commit()
    logger.info("backfill done, updated=%s", updated)


if __name__ == "__main__":
    asyncio.run(run())
