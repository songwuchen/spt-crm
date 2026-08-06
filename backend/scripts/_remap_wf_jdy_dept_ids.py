# -*- coding: utf-8 -*-
"""把流程条件里的简道云部门 MongoId 写成 CRM UUID（按部门名对齐）。"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import asyncpg

sys.stdout.reconfigure(encoding="utf-8")

MONGO = re.compile(r"^[0-9a-f]{24}$")
DEPT_FIELDS = {"department", "offices", "offices_multi", "department_multi"}
JDY_NAMES = {
    "56ca5b8af97e80434fc06122": "中央研究院",
    "56ca5b8af97e80434fc06124": "精细筛分装备销售部",
    "56ca5b8af97e80434fc06126": "冶金矿山装备销售事业部",
    "56ca5b8af97e80434fc06128": "国际营销中心",
    "56ca5b8af97e80434fc06133": "国际贸易一部",
    "56ca5b8af97e80434fc06141": "新乡研发中心",
    "56ca5b8af97e80434fc06142": "精品砂石事业部",
    "56ca5b8af97e80434fc06143": "清欠办",
    "56ca5b8af97e80434fc0614b": "郑州研发中心",
    "57f618b4cf0caf81d12d830b": "国际业务支持部",
    "59dc5c5f0b18743912395106": "新疆威猛工业智能装备有限公司",
    "5a9fa0ada21496c4066c2c4c": "（暂存）冶金装备销售事业部",
    "5aa37e54a21496c406944f49": "国际贸易二部",
    "5c500ac3a028fdc81b7a2ab9": "北京小威",
    "62c724bf70e58912be606334": "分布筛推广中心",
}


def load_dsn() -> str:
    for p in (Path(".env"), Path("../.env")):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                u = line.split("=", 1)[1].strip().strip('"').strip("'")
                return u.replace("postgresql+asyncpg://", "postgresql://")
    return "postgresql://postgres:postgres@localhost:5432/spt_crm"


def leaves(cond):
    if not isinstance(cond, dict):
        return
    nodes = cond.get("cond")
    if isinstance(nodes, list):
        for n in nodes:
            if isinstance(n, dict) and "cond" in n:
                yield from leaves(n)
            elif isinstance(n, dict) and n.get("field"):
                yield n
    elif cond.get("field"):
        yield cond


def remap_routes(routes, id_map):
    raw = json.loads(json.dumps(routes, ensure_ascii=False))
    replaced = 0
    for r in raw:
        if not isinstance(r, dict):
            continue
        for leaf in leaves(r.get("condition")):
            if str(leaf.get("field") or "") not in DEPT_FIELDS:
                continue
            val = leaf.get("value")
            if isinstance(val, list):
                nv = [id_map.get(str(v), v) for v in val]
                if nv != val:
                    leaf["value"] = nv
                    replaced += 1
            elif isinstance(val, str) and val in id_map:
                leaf["value"] = id_map[val]
                replaced += 1
    return raw, replaced


def has_jdy(routes) -> bool:
    for r in routes or []:
        if not isinstance(r, dict):
            continue
        for leaf in leaves(r.get("condition")):
            if str(leaf.get("field") or "") not in DEPT_FIELDS:
                continue
            val = leaf.get("value")
            for v in (val if isinstance(val, list) else [val]):
                if isinstance(v, str) and MONGO.match(v):
                    return True
    return False


async def main() -> None:
    conn = await asyncpg.connect(load_dsn())
    depts = await conn.fetch("SELECT tenant_id::text AS tid, id::text AS id, name FROM departments")
    by_tenant: dict[str, dict[str, str]] = {}
    for r in depts:
        by_tenant.setdefault(r["tid"], {})
        if r["name"] and r["name"] not in by_tenant[r["tid"]]:
            by_tenant[r["tid"]][r["name"]] = r["id"]

    rows = await conn.fetch(
        """
        SELECT v.id::text AS vid, d.code, d.name, d.tenant_id::text AS tid,
               v.version_number, v.status, v.route_definitions
        FROM wf_process_definition d
        JOIN wf_process_definition_version v ON v.process_definition_id = d.id
        WHERE d.is_deleted = false
        """
    )
    n = 0
    for row in rows:
        routes = row["route_definitions"]
        if isinstance(routes, str):
            routes = json.loads(routes)
        if not has_jdy(routes):
            continue
        id_map = {
            jid: by_tenant.get(row["tid"], {}).get(jname)
            for jid, jname in JDY_NAMES.items()
            if by_tenant.get(row["tid"], {}).get(jname)
        }
        # filter None
        id_map = {k: v for k, v in id_map.items() if v}
        new_routes, replaced = remap_routes(routes or [], id_map)
        if replaced <= 0:
            print(f"skip {row['code']} v{row['version_number']}: map={len(id_map)}")
            continue
        await conn.execute(
            "UPDATE wf_process_definition_version SET route_definitions=$1::jsonb, updated_at=NOW() WHERE id=$2",
            json.dumps(new_routes, ensure_ascii=False),
            row["vid"],
        )
        n += 1
        print(
            f"OK {row['name']} / {row['code']} v{row['version_number']} "
            f"status={row['status']} replaced={replaced} map={len(id_map)}"
        )
    print(f"done versions_updated={n}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
