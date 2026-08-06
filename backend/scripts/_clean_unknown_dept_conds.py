# -*- coding: utf-8 -*-
"""从流程连线条件中移除 CRM 不存在的部门 id（设计器「未知部门」）。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

TENANT = "00000000-0000-0000-0000-000000000001"
DEPT_FIELDS = frozenset({"department", "offices", "offices_multi", "department_multi"})


def load_dsn() -> str:
    import os

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


def clean_node(node: dict, valid: set[str], removed: list[str]) -> dict | None:
    if "cond" in node and isinstance(node.get("cond"), list):
        kept = []
        for child in node["cond"]:
            if not isinstance(child, dict):
                continue
            c = clean_node(child, valid, removed)
            if c is not None:
                kept.append(c)
        if not kept:
            return None
        out = dict(node)
        out["cond"] = kept
        return out

    field = str(node.get("field") or "")
    if field not in DEPT_FIELDS:
        return node

    val = node.get("value")
    if isinstance(val, list):
        kept_vals = []
        for v in val:
            s = str(v) if v is not None else ""
            if s in valid:
                kept_vals.append(v)
            elif s:
                removed.append(s)
        if not kept_vals:
            return None
        out = dict(node)
        out["value"] = kept_vals
        return out

    if val is None or val == "":
        return None
    s = str(val)
    if s in valid:
        return node
    removed.append(s)
    return None


def clean_routes(routes: list, valid: set[str]) -> tuple[list, dict]:
    raw = json.loads(json.dumps(routes, ensure_ascii=False))
    removed: list[str] = []
    touched = 0
    for r in raw:
        if not isinstance(r, dict):
            continue
        cond = r.get("condition")
        if not isinstance(cond, dict):
            continue
        before = json.dumps(cond, ensure_ascii=False, sort_keys=True)
        cleaned = clean_node(cond, valid, removed)
        after = json.dumps(cleaned, ensure_ascii=False, sort_keys=True) if cleaned else "null"
        if before != after:
            touched += 1
            r["condition"] = cleaned
    uniq = list(dict.fromkeys(removed))
    return raw, {"routes_touched": touched, "values_removed": len(removed), "removed_ids": uniq}


async def main() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(load_dsn())
    async with eng.begin() as conn:
        valid = {
            str(r[0])
            for r in (
                await conn.execute(
                    text("SELECT id FROM departments WHERE tenant_id = :t"),
                    {"t": TENANT},
                )
            ).all()
        }
        print(f"valid depts: {len(valid)}")

        rows = (
            await conn.execute(
                text(
                    """
                SELECT v.id, d.code, v.version_number, v.status, v.route_definitions
                FROM wf_process_definition_version v
                JOIN wf_process_definition d ON d.id = v.process_definition_id
                WHERE v.tenant_id = :t AND d.is_deleted = false
                """
                ),
                {"t": TENANT},
            )
        ).all()

        total_routes = total_vals = 0
        all_removed: set[str] = set()
        for vid, code, ver, status, routes in rows:
            routes = routes or []
            if isinstance(routes, str):
                routes = json.loads(routes)
            new_routes, stats = clean_routes(routes, valid)
            if not stats["routes_touched"]:
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
            total_routes += stats["routes_touched"]
            total_vals += stats["values_removed"]
            all_removed.update(stats["removed_ids"])
            print(
                f"  {code} v{ver}({status}): routes={stats['routes_touched']} "
                f"removed={stats['values_removed']}"
            )

        print(
            f"done: routes_touched={total_routes} values_removed={total_vals} "
            f"unique_ids={len(all_removed)}"
        )
        for i in sorted(all_removed):
            print(f"  - {i}")

    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
