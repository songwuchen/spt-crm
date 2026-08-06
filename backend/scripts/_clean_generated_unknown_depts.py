# -*- coding: utf-8 -*-
"""从内置生成图里清掉 CRM 不存在的部门 id，避免 ensure 再灌回「未知部门」。"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
TENANT = "00000000-0000-0000-0000-000000000001"
FILES = [
    ROOT / "app" / "domains" / "lowcode" / "_scheme_management_generated.py",
    ROOT / "app" / "domains" / "lowcode" / "_drawing_jdy_generated.py",
]
DEPT_FIELDS = frozenset({"department", "offices", "offices_multi", "department_multi"})


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
        kept_vals = [v for v in val if str(v) in valid]
        for v in val:
            s = str(v) if v is not None else ""
            if s and s not in valid:
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


def clean_obj(obj, valid: set[str], removed: list[str]):
    if isinstance(obj, dict):
        if "route_definitions" in obj and isinstance(obj["route_definitions"], list):
            for r in obj["route_definitions"]:
                if not isinstance(r, dict):
                    continue
                cond = r.get("condition")
                if isinstance(cond, dict):
                    r["condition"] = clean_node(cond, valid, removed)
        for v in obj.values():
            clean_obj(v, valid, removed)
    elif isinstance(obj, list):
        for x in obj:
            clean_obj(x, valid, removed)


async def main() -> None:
    eng = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/spt_crm")
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
    await eng.dispose()
    print("valid", len(valid))

    for path in FILES:
        if not path.exists():
            print("skip missing", path)
            continue
        text_src = path.read_text(encoding="utf-8")
        # VAR = json.loads(r'''...''')
        m = re.search(r"(= json\.loads\(r''')(\{.*)('''\))", text_src, re.S)
        if not m:
            print("no json payload", path.name)
            continue
        payload = json.loads(m.group(2))
        removed: list[str] = []
        clean_obj(payload, valid, removed)
        uniq = sorted(set(removed))
        new_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        path.write_text(
            text_src[: m.start(2)] + new_json + text_src[m.end(2) :],
            encoding="utf-8",
        )
        print(f"{path.name}: removed {len(removed)} values, unique={len(uniq)}")
        for i in uniq:
            print(" ", i)


if __name__ == "__main__":
    asyncio.run(main())
