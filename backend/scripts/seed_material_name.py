# -*- coding: utf-8 -*-
"""安装「物料名称」内置表单，并从 docs dump 导入简道云选项。

Idempotent：同名 name 已存在则跳过。

  python -m scripts.seed_material_name
  python -m scripts.seed_material_name <tenant_id>
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select, text

from app.database import async_session_factory, generate_uuid
from app.domains.lowcode import service as lc_svc
from app.domains.lowcode.models import FormInstance
from app.domains.tenant.models import PlatformTenant

DOCS = Path(__file__).resolve().parents[2] / "docs" / "product"
CODE = "material_name"
OPTIONS_FILE = "_jdy_material_name_options.json"
DATA_FILE = "_jdy_material_name_data.json"
JDY_NAME_FIELD = "_widget_1685082925104"


def _load_names() -> list[str]:
    p = DOCS / OPTIONS_FILE
    if p.exists():
        raw = json.loads(p.read_text(encoding="utf-8"))
        items = ((raw.get("data") or {}).get("items") or []) if isinstance(raw, dict) else []
        out: list[str] = []
        for x in items:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
            elif isinstance(x, dict):
                n = str(x.get("text") or x.get("value") or x.get("label") or "").strip()
                if n:
                    out.append(n)
        return _uniq(out)
    data_p = DOCS / DATA_FILE
    if not data_p.exists():
        raise FileNotFoundError(
            f"missing {p} (run scripts._pull_jdy_material_name first)"
        )
    raw = json.loads(data_p.read_text(encoding="utf-8"))
    rows = ((raw.get("data") or {}).get("items") or []) if isinstance(raw, dict) else []
    names: list[str] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        n = str(r.get(JDY_NAME_FIELD) or r.get("name") or "").strip()
        if n:
            names.append(n)
    return _uniq(names)


def _uniq(names: list[str]) -> list[str]:
    seen: set[str] = set()
    uniq: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


async def _pick_user_id(db, tenant_id: str) -> str:
    for sql in (
        "SELECT id FROM users WHERE tenant_id = :t AND COALESCE(is_deleted, false) = false "
        "ORDER BY created_at ASC NULLS LAST LIMIT 1",
        "SELECT id FROM users WHERE tenant_id = :t ORDER BY created_at ASC NULLS LAST LIMIT 1",
        "SELECT id FROM users WHERE tenant_id = :t LIMIT 1",
    ):
        try:
            row = (await db.execute(text(sql), {"t": tenant_id})).first()
            if row and row[0]:
                return str(row[0])
        except Exception:
            await db.rollback()
    return "00000000-0000-0000-0000-000000000000"


async def seed_tenant(db, tenant_id: str) -> dict:
    user_id = await _pick_user_id(db, tenant_id)
    user = {"sub": user_id, "real_name": "system", "username": "system", "roles": []}
    names = _load_names()
    print(f"[{tenant_id[:8]}] initiator={user_id} source={len(names)}")
    tpl = await lc_svc.ensure_builtin_form(db, tenant_id, CODE, user)
    published = await lc_svc.get_published_version(db, tenant_id, tpl.id)
    if not published:
        raise RuntimeError(f"builtin {CODE} has no published version")
    field_defs = published.field_definitions or [
        {"id": "name", "type": "text", "label": "物料名称", "required": True},
    ]

    existing_rows = (
        await db.execute(
            select(FormInstance).where(
                FormInstance.tenant_id == tenant_id,
                FormInstance.template_id == tpl.id,
                FormInstance.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    existing_names: set[str] = set()
    for inst in existing_rows:
        fd = inst.form_data if isinstance(inst.form_data, dict) else {}
        n = str(fd.get("name") or "").strip()
        if n:
            existing_names.add(n)

    added = 0
    skipped = 0
    for name in names:
        if name in existing_names:
            skipped += 1
            continue
        inst = FormInstance(
            id=generate_uuid(),
            tenant_id=tenant_id,
            template_id=tpl.id,
            template_version_id=published.id,
            title=name,
            status="submitted",
            form_data={"name": name},
            field_definitions=field_defs,
            created_by=user_id,
            initiator_id=user_id,
        )
        db.add(inst)
        existing_names.add(name)
        added += 1
    await db.commit()
    stats = {
        "template_id": tpl.id,
        "source_count": len(names),
        "added": added,
        "skipped": skipped,
        "total": len(existing_names),
    }
    print(f"[{tenant_id[:8]}] {CODE}: +{added} skip={skipped} total={len(existing_names)}")
    return stats


async def _discover_tenant_ids(session) -> list[str]:
    tenants = (await session.execute(select(PlatformTenant))).scalars().all()
    if tenants:
        return [t.id for t in tenants]
    rows = (await session.execute(text("SELECT DISTINCT tenant_id FROM users"))).all()
    return [r[0] for r in rows if r[0]]


async def main() -> None:
    tenant_arg = sys.argv[1] if len(sys.argv) > 1 else None
    async with async_session_factory() as db:
        if tenant_arg:
            tenant_ids = [tenant_arg]
        else:
            tenant_ids = await _discover_tenant_ids(db)
            if not tenant_ids:
                tenant_ids = ["00000000-0000-0000-0000-000000000001"]
        for tid in tenant_ids:
            await seed_tenant(db, tid)
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
