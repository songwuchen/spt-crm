# -*- coding: utf-8 -*-
"""给已发布流程同源多出边打 exclusive_group（简道云 if/else 互斥）。

不改条件内容；并行能力保留在无 exclusive_group 的边上。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

TENANT = None  # None = 全部租户
# 重点修方案/图纸类；也可扫全量
CODES = (
    "SYS_SCHEME_MANAGEMENT",
    "SYS_DRAWING_REQUISITION",
    "SYS_INSTALL_DRAWING_NOTICE",
)


def load_dsn() -> str:
    env = os.environ.get("DATABASE_URL")
    if env:
        dsn = env.strip().strip('"').strip("'")
        if dsn.startswith("postgresql://"):
            dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
        return dsn
    dsn = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/spt_crm"
    for p in (Path(".env"), Path("../.env")):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
                if dsn.startswith("postgresql://"):
                    dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    return dsn


def mark_exclusive(routes: list) -> tuple[list, int]:
    raw = json.loads(json.dumps(routes or [], ensure_ascii=False))
    by_src: dict[str, list] = {}
    for r in raw:
        if not isinstance(r, dict) or r.get("always"):
            continue
        by_src.setdefault(r.get("source") or "", []).append(r)
    touched = 0
    for src, outs in by_src.items():
        if len(outs) < 2:
            continue
        gid = f"ex_{src}"
        changed = False
        for r in outs:
            if r.get("exclusive_group") != gid:
                r["exclusive_group"] = gid
                changed = True
        if changed:
            touched += 1
    return raw, touched


async def main() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(load_dsn())
    async with eng.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                SELECT v.id, d.code, v.version_number, v.status, v.route_definitions, d.tenant_id
                FROM wf_process_definition_version v
                JOIN wf_process_definition d ON d.id = v.process_definition_id
                WHERE d.is_deleted = false
                  AND d.code IN ('SYS_SCHEME_MANAGEMENT','SYS_DRAWING_REQUISITION','SYS_INSTALL_DRAWING_NOTICE')
                """
                )
            )
        ).all()
        total = 0
        for vid, code, ver, status, routes, tenant_id in rows:
            new_routes, n = mark_exclusive(routes or [])
            if not n:
                continue
            await conn.execute(
                text(
                    """
                    UPDATE wf_process_definition_version
                    SET route_definitions = CAST(:routes AS jsonb)
                    WHERE id = :id
                    """
                ),
                {"id": vid, "routes": json.dumps(new_routes, ensure_ascii=False)},
            )
            total += n
            print(f"  [{tenant_id[:8]}] {code} v{ver}({status}): sources_marked={n}")
        print(f"done: source_groups={total}")
    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
