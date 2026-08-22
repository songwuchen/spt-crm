#!/usr/bin/env python3
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8")

from app.database import async_session_factory
from app.domains.lowcode.service import ensure_builtin_form, get_published_version

TID = "00000000-0000-0000-0000-000000000001"
SUB = "00000000-0000-0000-0000-000000000010"


async def main() -> None:
    async with async_session_factory() as db:
        tpl = await ensure_builtin_form(db, TID, "prod_card_supplement", {"sub": SUB})
        ver = await get_published_version(db, TID, tpl.id)
        defs = (ver.field_definitions if ver else []) or []
        by = {f.get("id"): f for f in defs if isinstance(f, dict)}
        for fid in ("drawing_no_query", "no_sales_person", "region_manager", "yes_customer_name",
                    "no_drawing_no", "prod_card_line_items"):
            f = by.get(fid) or {}
            print(fid, "type=", f.get("type"), "on_create=", f.get("available_on_create"),
                  "form_editable=", f.get("form_editable"),
                  "contract_fill=", (f.get("props") or {}).get("contract_fill"))


if __name__ == "__main__":
    asyncio.run(main())
