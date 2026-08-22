#!/usr/bin/env python3
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8")

from app.database import async_session_factory
from app.domains.lowcode.service import ensure_builtin_form

TID = "00000000-0000-0000-0000-000000000001"
SUB = "00000000-0000-0000-0000-000000000010"


async def main() -> None:
    async with async_session_factory() as db:
        tpl = await ensure_builtin_form(db, TID, "prod_card_supplement", {"sub": SUB})
        await db.commit()
        by = {f.get("id"): f for f in (tpl.field_definitions or []) if isinstance(f, dict)}
        for fid in ("drawing_no_query", "no_sales_person", "region_manager", "yes_customer_name"):
            f = by.get(fid) or {}
            print(fid, "type=", f.get("type"), "form_editable=", f.get("form_editable"),
                  "contract_fill=", (f.get("props") or {}).get("contract_fill"))


if __name__ == "__main__":
    asyncio.run(main())
