# -*- coding: utf-8 -*-
"""远程可选范围：用 Python 在 backend 容器内按姓名解析并写入（避免 SQL 中文/编码坑）。"""
from __future__ import annotations

import json
import textwrap

import paramiko

HOST = "192.168.0.39"
USER = "songwuchen"
PWD = "Ruolin2025"

REMOTE_PY = textwrap.dedent(
    r'''
# -*- coding: utf-8 -*-
import json
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

ROOM_LEADERS = ["周彦立", "李兴玉", "樊磊", "刘松潮", "吕芹", "曹修国", "丰芊", "王东明", "赵小康"]
TRANSFER_PACKAGING = ["杨光", "赵连华", "李海春", "王昌轲"]
SCHEME_OFFICES = [
    "中央研究院", "设计一室", "设计二室", "新乡研发中心", "郑州研发中心",
    "分布筛研发中心", "审核组", "电气组", "筛板组", "振源组", "研管办",
    "研发中心*研发试验组",
]
TENANTS = [
    "00000000-0000-0000-0000-000000000001",
    "9365954a-a6b3-461a-b478-27e786b08c78",
]

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def connect():
    import os
    url = os.environ.get("DATABASE_URL") or ""
    # postgresql+asyncpg://user:pass@host:5432/db  or postgresql://...
    if url.startswith("postgresql"):
        # strip +asyncpg / +psycopg2
        url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
            "postgresql+psycopg2://", "postgresql://"
        )
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "spt_crm"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )

def user_ids(cur, tid, names):
    cur.execute(
        """
        SELECT DISTINCT ON (real_name) id::text, real_name
        FROM users
        WHERE tenant_id::text = %s AND is_active = true AND real_name = ANY(%s)
        ORDER BY real_name, id
        """,
        (tid, names),
    )
    rows = cur.fetchall()
    found = {r[1]: r[0] for r in rows}
    missing = [n for n in names if n not in found]
    return [found[n] for n in names if n in found], missing

def dept_ids(cur, tid, names):
    cur.execute(
        """
        SELECT DISTINCT ON (name) id::text, name, path
        FROM departments
        WHERE tenant_id::text = %s AND name = ANY(%s)
        ORDER BY name,
          CASE
            WHEN path LIKE %s THEN 0
            WHEN path LIKE %s THEN 1
            ELSE 2
          END,
          length(coalesce(path, ''))
        """,
        (tid, names, "%中央研究院%", "%技术总工%"),
    )
    rows = cur.fetchall()
    found = {r[1]: r[0] for r in rows}
    missing = [n for n in names if n not in found]
    return [found[n] for n in names if n in found], missing, {r[1]: r[2] for r in rows}

def upsert_scope(cur, tid, code, name, kind, description, rules):
    cur.execute(
        "SELECT id FROM pickable_scopes WHERE tenant_id::text=%s AND code=%s",
        (tid, code),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            """
            UPDATE pickable_scopes
            SET name=%s, kind=%s, description=%s, is_system=true, rules=%s::jsonb, updated_at=%s
            WHERE id=%s
            """,
            (name, kind, description, json.dumps(rules, ensure_ascii=False), now(), row[0]),
        )
    else:
        cur.execute(
            """
            INSERT INTO pickable_scopes
              (id, tenant_id, code, name, kind, description, is_system, rules, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,true,%s::jsonb,%s,%s)
            """,
            (str(uuid.uuid4()), tid, code, name, kind, description,
             json.dumps(rules, ensure_ascii=False), now(), now()),
        )

def patch_transfer_field(cur):
    cur.execute(
        """
        SELECT v.id, v.field_definitions
        FROM lc_form_template_version v
        JOIN lc_form_template t ON t.id = v.template_id
        WHERE t.code IN ('scheme_management', 'drawing_requisition')
          AND v.status IN ('published', 'draft')
        """
    )
    for vid, fields in cur.fetchall():
        if not isinstance(fields, list):
            continue
        changed = False
        new_fields = []
        for f in fields:
            if not isinstance(f, dict):
                new_fields.append(f)
                continue
            if f.get("id") == "transfer_packaging_users":
                props = dict(f.get("props") or {})
                scope = props.get("pickable_scope") if isinstance(props.get("pickable_scope"), dict) else {}
                if scope.get("scope_code") != "fa-zxxgy":
                    props["pickable_scope"] = {"scope_code": "fa-zxxgy"}
                    f = dict(f)
                    f["props"] = props
                    changed = True
            new_fields.append(f)
        if changed:
            cur.execute(
                "UPDATE lc_form_template_version SET field_definitions=%s::jsonb WHERE id=%s",
                (json.dumps(new_fields, ensure_ascii=False), vid),
            )
            print("patched template version", vid)

def main():
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        for tid in TENANTS:
            cur.execute("SELECT 1 FROM platform_tenants WHERE id::text=%s", (tid,))
            if not cur.fetchone():
                print("skip missing tenant", tid)
                continue
            uids, miss_u = user_ids(cur, tid, ROOM_LEADERS)
            packs, miss_p = user_ids(cur, tid, TRANSFER_PACKAGING)
            dids, miss_d, paths = dept_ids(cur, tid, SCHEME_OFFICES)
            print("tenant", tid)
            print("  room_leaders", len(uids), "missing", miss_u)
            print("  fa-zxxgy", len(packs), "missing", miss_p)
            print("  offices", len(dids), "missing", miss_d)
            for n, p in paths.items():
                print("   ", n, "->", p)
            upsert_scope(
                cur, tid, "room_leaders", "方案管理-设计指派", "person",
                "方案管理「设计指派」人选范围；在此直接勾选成员。",
                {"role_codes": [], "user_ids": uids, "dept_ids": [], "include_children": True},
            )
            upsert_scope(
                cur, tid, "fa-zxxgy", "方案管理-转新乡、工艺包装", "person",
                "方案管理「转新乡、工艺包装」人选范围；在此直接勾选成员。",
                {"role_codes": [], "user_ids": packs, "dept_ids": [], "include_children": True},
            )
            upsert_scope(
                cur, tid, "scheme_offices", "方案管理-科室", "department",
                "方案管理「科室」可选部门范围。",
                {"role_codes": [], "user_ids": [], "dept_ids": dids, "include_children": True},
            )
        patch_transfer_field(cur)
        conn.commit()
        print("COMMIT OK")
        # verify default tenant names
        tid = TENANTS[0]
        for code in ("room_leaders", "fa-zxxgy"):
            cur.execute(
                """
                SELECT u.real_name
                FROM pickable_scopes s
                CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'user_ids') uid
                JOIN users u ON u.id::text = uid
                WHERE s.tenant_id::text=%s AND s.code=%s
                ORDER BY u.real_name
                """,
                (tid, code),
            )
            print(code, [r[0] for r in cur.fetchall()])
        cur.execute(
            """
            SELECT d.name
            FROM pickable_scopes s
            CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'dept_ids') did
            JOIN departments d ON d.id::text = did
            WHERE s.tenant_id::text=%s AND s.code='scheme_offices'
            ORDER BY d.name
            """,
            (tid,),
        )
        print("scheme_offices", [r[0] for r in cur.fetchall()])
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
'''
)


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=25, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_sync_pickable_py.py", "w") as f:
        f.write(REMOTE_PY)
    sftp.close()
    cmd = (
        "docker cp /tmp/_sync_pickable_py.py spt-crm-backend-1:/tmp/_sync_pickable_py.py && "
        "docker exec -i spt-crm-backend-1 python /tmp/_sync_pickable_py.py"
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
