# -*- coding: utf-8 -*-
"""把已发布流程里「部门审批/设计主管审批」的 dept_head 改成 form_field_dept。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import asyncpg

sys.stdout.reconfigure(encoding="utf-8")

TARGET_NAMES = {"部门审批", "设计主管审批"}
CODES = (
    "SYS_SCHEME_MANAGEMENT",
    "SYS_DRAWING_REQUISITION",
    "SYS_INSTALL_DRAWING_NOTICE",
)


def load_dsn() -> str:
    for p in (Path(".env"), Path("../.env")):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                    .strip("'")
                    .replace("postgresql+asyncpg://", "postgresql://")
                )
    return "postgresql://postgres:postgres@localhost:5432/spt_crm"


def patch_nodes(nodes: list) -> tuple[list, int]:
    raw = json.loads(json.dumps(nodes, ensure_ascii=False))
    n = 0
    for node in raw:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "approval":
            continue
        if (node.get("name") or "") not in TARGET_NAMES:
            continue
        rule = node.get("approver_rule") or {}
        if rule.get("type") != "dept_head":
            continue
        node["approver_rule"] = {"type": "form_field_dept", "value": "department"}
        n += 1
    return raw, n


async def main() -> None:
    conn = await asyncpg.connect(load_dsn())
    rows = await conn.fetch(
        """
        SELECT v.id::text AS vid, d.code, v.version_number, v.status, v.node_definitions
        FROM wf_process_definition d
        JOIN wf_process_definition_version v ON v.process_definition_id = d.id
        WHERE d.is_deleted = false AND d.code = ANY($1::text[])
        """,
        list(CODES),
    )
    touched = 0
    for row in rows:
        nodes = row["node_definitions"]
        if isinstance(nodes, str):
            nodes = json.loads(nodes)
        new_nodes, changed = patch_nodes(nodes or [])
        if changed <= 0:
            continue
        await conn.execute(
            "UPDATE wf_process_definition_version SET node_definitions=$1::jsonb, updated_at=NOW() WHERE id=$2",
            json.dumps(new_nodes, ensure_ascii=False),
            row["vid"],
        )
        touched += 1
        print(
            f"OK {row['code']} v{row['version_number']} status={row['status']} patched={changed}"
        )
    print(f"done versions={touched}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
