# -*- coding: utf-8 -*-
"""在 0.39 backend 容器内用 asyncpg 同步可选范围（与本地名单一致）。"""
from __future__ import annotations

import textwrap

import paramiko

HOST = "192.168.0.39"
USER = "songwuchen"
PWD = "Ruolin2025"

REMOTE_PY = textwrap.dedent(
    r'''
# -*- coding: utf-8 -*-
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import asyncpg

ROOM_LEADERS = ["周彦立", "李兴玉", "樊磊", "刘松潮", "吕芹", "曹修国", "丰芊", "王东明", "赵小康"]
TRANSFER_PACKAGING = ["杨光", "赵连华", "李海春", "王昌轲"]
SCHEME_OFFICES = [
    "中央研究院", "设计一室", "设计二室", "新乡研发中心", "郑州研发中心",
    "分布筛研发中心", "审核组", "电气组", "筛板组", "振源组", "研管办",
    "研发中心*研发试验组",
]
DEFAULT_TID = "00000000-0000-0000-0000-000000000001"


def dsn() -> str:
    url = os.environ.get("DATABASE_URL") or ""
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    if url.startswith("postgresql://"):
        return url
    host = os.environ.get("POSTGRES_HOST") or os.environ.get("DB_HOST") or "db"
    port = os.environ.get("POSTGRES_PORT") or "5432"
    db = os.environ.get("POSTGRES_DB") or "spt_crm"
    user = os.environ.get("POSTGRES_USER") or "postgres"
    pwd = os.environ.get("POSTGRES_PASSWORD") or "postgres"
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


async def user_ids(conn, tid, names):
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (real_name) id::text AS id, real_name
        FROM users
        WHERE tenant_id::text = $1 AND is_active = true AND real_name = ANY($2::text[])
        ORDER BY real_name, id
        """,
        tid, names,
    )
    found = {r["real_name"]: r["id"] for r in rows}
    missing = [n for n in names if n not in found]
    return [found[n] for n in names if n in found], missing


async def dept_ids(conn, tid, names):
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (name) id::text AS id, name, path
        FROM departments
        WHERE tenant_id::text = $1 AND name = ANY($2::text[])
        ORDER BY name,
          CASE
            WHEN path LIKE '%中央研究院%' THEN 0
            WHEN path LIKE '%技术总工%' THEN 1
            ELSE 2
          END,
          length(coalesce(path, ''))
        """,
        tid, names,
    )
    found = {r["name"]: r["id"] for r in rows}
    missing = [n for n in names if n not in found]
    return [found[n] for n in names if n in found], missing


async def upsert_scope(conn, tid, code, name, kind, description, rules):
    row = await conn.fetchrow(
        "SELECT id FROM pickable_scopes WHERE tenant_id::text=$1 AND code=$2",
        tid, code,
    )
    rules_json = json.dumps(rules, ensure_ascii=False)
    ts = datetime.now(timezone.utc).replace(tzinfo=None)
    if row:
        await conn.execute(
            """
            UPDATE pickable_scopes
            SET name=$1, kind=$2, description=$3, is_system=true,
                rules=$4::jsonb, updated_at=$5
            WHERE id=$6
            """,
            name, kind, description, rules_json, ts, row["id"],
        )
    else:
        await conn.execute(
            """
            INSERT INTO pickable_scopes
              (id, tenant_id, code, name, kind, description, is_system, rules, created_at, updated_at)
            VALUES ($1,$2::uuid,$3,$4,$5,$6,true,$7::jsonb,$8,$8)
            """,
            str(uuid.uuid4()), tid, code, name, kind, description, rules_json, ts,
        )


async def patch_transfer_field(conn):
    rows = await conn.fetch(
        """
        SELECT v.id, v.field_definitions
        FROM lc_form_template_version v
        JOIN lc_form_template t ON t.id = v.template_id
        WHERE t.code = ANY($1::text[])
          AND v.status = ANY($2::text[])
        """,
        ["scheme_management", "drawing_requisition"],
        ["published", "draft"],
    )
    for row in rows:
        fields = row["field_definitions"]
        if isinstance(fields, str):
            fields = json.loads(fields)
        if not isinstance(fields, list):
            continue
        changed = False
        new_fields = []
        for f in fields:
            if isinstance(f, dict) and f.get("id") == "transfer_packaging_users":
                props = dict(f.get("props") or {})
                scope = props.get("pickable_scope") if isinstance(props.get("pickable_scope"), dict) else {}
                if scope.get("scope_code") != "fa-zxxgy":
                    props["pickable_scope"] = {"scope_code": "fa-zxxgy"}
                    f = dict(f)
                    f["props"] = props
                    changed = True
            new_fields.append(f)
        if changed:
            await conn.execute(
                "UPDATE lc_form_template_version SET field_definitions=$1::jsonb WHERE id=$2",
                json.dumps(new_fields, ensure_ascii=False), row["id"],
            )
            print("patched template version", row["id"])


async def main():
    print("DSN host part:", dsn().split("@")[-1])
    conn = await asyncpg.connect(dsn())
    try:
        # 远程默认租户可能不在 platform_tenants，但仍有 users/departments
        tids = [DEFAULT_TID]
        extra = await conn.fetch(
            """
            SELECT DISTINCT tenant_id::text AS tid FROM users
            WHERE tenant_id::text <> $1
            ORDER BY 1
            """,
            DEFAULT_TID,
        )
        for r in extra:
            tids.append(r["tid"])
        print("tenants to sync:", tids)

        for tid in tids:
            uids, miss_u = await user_ids(conn, tid, ROOM_LEADERS)
            packs, miss_p = await user_ids(conn, tid, TRANSFER_PACKAGING)
            dids, miss_d = await dept_ids(conn, tid, SCHEME_OFFICES)
            print("tenant", tid)
            print("  room_leaders", len(uids), [n for n in ROOM_LEADERS if n not in miss_u], "missing", miss_u)
            print("  fa-zxxgy", len(packs), [n for n in TRANSFER_PACKAGING if n not in miss_p], "missing", miss_p)
            print("  offices", len(dids), [n for n in SCHEME_OFFICES if n not in miss_d], "missing", miss_d)
            if not uids and not packs and not dids:
                print("  skip empty tenant")
                continue
            await upsert_scope(
                conn, tid, "room_leaders", "方案管理-设计指派", "person",
                "方案管理「设计指派」人选范围；在此直接勾选成员。",
                {"role_codes": [], "user_ids": uids, "dept_ids": [], "include_children": True},
            )
            await upsert_scope(
                conn, tid, "fa-zxxgy", "方案管理-转新乡、工艺包装", "person",
                "方案管理「转新乡、工艺包装」人选范围；在此直接勾选成员。",
                {"role_codes": [], "user_ids": packs, "dept_ids": [], "include_children": True},
            )
            await upsert_scope(
                conn, tid, "scheme_offices", "方案管理-科室", "department",
                "方案管理「科室」可选部门范围。",
                {"role_codes": [], "user_ids": [], "dept_ids": dids, "include_children": True},
            )
        await patch_transfer_field(conn)
        print("COMMIT OK")
        tid = DEFAULT_TID
        for code in ("room_leaders", "fa-zxxgy"):
            rows = await conn.fetch(
                """
                SELECT u.real_name
                FROM pickable_scopes s
                CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'user_ids') AS uid
                JOIN users u ON u.id::text = uid
                WHERE s.tenant_id::text=$1 AND s.code=$2
                ORDER BY u.real_name
                """,
                tid, code,
            )
            print(code, [r["real_name"] for r in rows])
        rows = await conn.fetch(
            """
            SELECT d.name
            FROM pickable_scopes s
            CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'dept_ids') AS did
            JOIN departments d ON d.id::text = did
            WHERE s.tenant_id::text=$1 AND s.code='scheme_offices'
            ORDER BY d.name
            """,
            tid,
        )
        print("scheme_offices", [r["name"] for r in rows])
    finally:
        await conn.close()


asyncio.run(main())
'''
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=25, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    with sftp.open("/tmp/_sync_pickable_async.py", "wb") as f:
        f.write(REMOTE_PY.encode("utf-8"))
    sftp.close()
    cmd = (
        "docker cp /tmp/_sync_pickable_async.py spt-crm-backend-1:/tmp/_sync_pickable_async.py && "
        "docker exec -i spt-crm-backend-1 python /tmp/_sync_pickable_async.py"
    )
    print(">>>", cmd)
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("ERR:", err[-3000:])
    print("[exit", code, "]")
    c.close()


if __name__ == "__main__":
    main()
