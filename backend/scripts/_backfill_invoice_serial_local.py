#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地回刷开票申请历史流水号（KPSQ- + 5位序号）。

用法（backend 目录）:
  python scripts/_backfill_invoice_serial_local.py --dry-run
  python scripts/_backfill_invoice_serial_local.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import delete, select, text
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session_factory
from app.domains.lowcode.invoice_application_fields import (
    INVOICE_SERIAL_NO_RULES,
    INVOICE_SERIAL_PREFIX,
    apply_invoice_application_fields,
)
from app.domains.lowcode.models import FormInstance, FormTemplate, FormTemplateVersion, SerialCounter
from app.domains.lowcode.serial_number import generate_serial_value
from app.domains.lowcode.service import _pick_business_no, ensure_builtin_form

SYS_USER = {"sub": "00000000-0000-0000-0000-000000000001"}


def _needs_serial_fix(data: dict, business_no: str | None) -> bool:
    serial = str(data.get("serial_no") or "").strip()
    return not serial.startswith(INVOICE_SERIAL_PREFIX)


async def _published_defs(db, tpl: FormTemplate) -> list[dict]:
    ver = (await db.execute(
        select(FormTemplateVersion).where(
            FormTemplateVersion.template_id == tpl.id,
            FormTemplateVersion.status == "published",
        ).order_by(FormTemplateVersion.version_number.desc()).limit(1)
    )).scalar_one_or_none()
    return list((ver.field_definitions if ver else None) or [])


async def backfill(*, dry_run: bool) -> int:
    async with async_session_factory() as db:
        tpl = (await db.execute(
            select(FormTemplate).where(
                FormTemplate.code == "invoice_application",
                FormTemplate.is_deleted == False,  # noqa: E712
            ).limit(1)
        )).scalar_one_or_none()
        if not tpl:
            print("本地无 invoice_application 模板")
            return 0

        print(f"template={tpl.id} tenant={tpl.tenant_id}")
        if not dry_run:
            tpl = await ensure_builtin_form(db, tpl.tenant_id, "invoice_application", SYS_USER)
            await db.commit()
            print("ensured builtin invoice_application")

        defs = await _published_defs(db, tpl)
        apply_invoice_application_fields(defs)
        sn_fd = next((f for f in defs if f.get("id") == "serial_no"), None)
        if not sn_fd or sn_fd.get("type") != "auto_number":
            print("serial_no 未配置为 auto_number，请先 ensure 模板")
            return 0
        rules = (sn_fd.get("props") or {}).get("serial_rules") or []
        print("serial_rules", rules or INVOICE_SERIAL_NO_RULES)

        rows = (await db.execute(
            select(FormInstance).where(
                FormInstance.template_id == tpl.id,
                FormInstance.is_deleted == False,  # noqa: E712
            ).order_by(FormInstance.created_at.asc())
        )).scalars().all()
        todo = [
            inst for inst in rows
            if _needs_serial_fix(dict(inst.form_data or {}), inst.business_no)
        ]
        print(f"instances={len(rows)} need_fix={len(todo)}")

        if not todo:
            return 0

        if dry_run:
            for inst in todo:
                data = dict(inst.form_data or {})
                print(
                    f"  would {inst.id[:8]} "
                    f"biz={inst.business_no!r} drawing={data.get('drawing_no')!r} "
                    f"serial={data.get('serial_no')!r}"
                )
            return len(todo)

        cleared = (await db.execute(
            delete(SerialCounter).where(
                SerialCounter.tenant_id == tpl.tenant_id,
                SerialCounter.template_id == tpl.id,
                SerialCounter.field_id == "serial_no",
            )
        )).rowcount or 0
        print(f"cleared serial counters={cleared}")

        changed = 0
        for inst in rows:
            data = dict(inst.form_data or {})
            if not _needs_serial_fix(data, inst.business_no):
                continue
            old_sn = data.get("serial_no")
            old_biz = inst.business_no
            data.pop("serial_no", None)
            serial = await generate_serial_value(
                db, inst.tenant_id, tpl.id, sn_fd, data, defs,
            )
            data["serial_no"] = serial
            inst.form_data = data
            flag_modified(inst, "form_data")
            inst.business_no = (_pick_business_no(data, defs) or serial)[:64]
            await db.execute(text("""
                UPDATE wf_process_instance
                SET business_no = :biz
                WHERE form_instance_id = :fid AND (business_no IS NULL OR business_no = :old_biz)
            """), {"biz": inst.business_no, "fid": inst.id, "old_biz": old_biz})
            print(
                f"  {inst.id[:8]} serial {old_sn!r}→{serial} "
                f"biz {old_biz!r}→{inst.business_no} drawing={data.get('drawing_no')!r}"
            )
            changed += 1

        await db.commit()
        print(f"done changed={changed}")
        return changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    n = asyncio.run(backfill(dry_run=args.dry_run))
    if args.dry_run:
        print(f"dry-run would change {n}")


if __name__ == "__main__":
    main()
