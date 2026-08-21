# -*- coding: utf-8 -*-
"""把本地可选范围人员/科室同步到 192.168.0.39 CRM（按姓名匹配远程 UUID）。"""
from __future__ import annotations

import paramiko

HOST = "192.168.0.39"
USER = "songwuchen"
PWD = "Ruolin2025"

# 与本地 pickable_scopes 对齐
ROOM_LEADERS = [
    "周彦立", "李兴玉", "樊磊", "刘松潮", "吕芹",
    "曹修国", "丰芊", "王东明", "赵小康",
]
TRANSFER_PACKAGING = ["杨光", "赵连华", "李海春", "王昌轲"]
SCHEME_OFFICES = [
    "中央研究院",
    "设计一室",
    "设计二室",
    "新乡研发中心",
    "郑州研发中心",
    "分布筛研发中心",
    "审核组",
    "电气组",
    "筛板组",
    "振源组",
    "研管办",
    "研发中心*研发试验组",
]

ROOM_SQL = ", ".join("'" + n.replace("'", "''") + "'" for n in ROOM_LEADERS)
PACK_SQL = ", ".join("'" + n.replace("'", "''") + "'" for n in TRANSFER_PACKAGING)
OFFICE_SQL = ", ".join("'" + n.replace("'", "''") + "'" for n in SCHEME_OFFICES)

SQL = f"""
DO $$
DECLARE
  tid text;
  uids jsonb;
  dids jsonb;
  pack_uids jsonb;
  r record;
BEGIN
  FOR r IN
    SELECT id::text AS tid
    FROM platform_tenants
    WHERE id::text IN (
      '00000000-0000-0000-0000-000000000001',
      '9365954a-a6b3-461a-b478-27e786b08c78'
    )
    OR code IN ('default', 'xiaowei')
  LOOP
    tid := r.tid;

    -- 预置三条范围（不存在则建）
    INSERT INTO pickable_scopes (id, tenant_id, code, name, kind, description, is_system, rules, created_at, updated_at)
    SELECT gen_random_uuid(), tid, 'room_leaders', '方案管理-设计指派', 'person',
           '方案管理「设计指派」人选范围；在此直接勾选成员。', true,
           '{{"role_codes":[],"user_ids":[],"dept_ids":[],"include_children":true}}'::jsonb,
           NOW(), NOW()
    WHERE NOT EXISTS (
      SELECT 1 FROM pickable_scopes WHERE tenant_id::text = tid AND code = 'room_leaders'
    );

    INSERT INTO pickable_scopes (id, tenant_id, code, name, kind, description, is_system, rules, created_at, updated_at)
    SELECT gen_random_uuid(), tid, 'scheme_offices', '方案管理-科室', 'department',
           '方案管理「科室」可选部门范围。', true,
           '{{"role_codes":[],"user_ids":[],"dept_ids":[],"include_children":true}}'::jsonb,
           NOW(), NOW()
    WHERE NOT EXISTS (
      SELECT 1 FROM pickable_scopes WHERE tenant_id::text = tid AND code = 'scheme_offices'
    );

    INSERT INTO pickable_scopes (id, tenant_id, code, name, kind, description, is_system, rules, created_at, updated_at)
    SELECT gen_random_uuid(), tid, 'fa-zxxgy', '方案管理-转新乡、工艺包装', 'person',
           '方案管理「转新乡、工艺包装」人选范围；在此直接勾选成员。', true,
           '{{"role_codes":[],"user_ids":[],"dept_ids":[],"include_children":true}}'::jsonb,
           NOW(), NOW()
    WHERE NOT EXISTS (
      SELECT 1 FROM pickable_scopes WHERE tenant_id::text = tid AND code = 'fa-zxxgy'
    );

    -- 设计指派：按姓名匹配本租户用户
    SELECT COALESCE(jsonb_agg(id::text ORDER BY real_name), '[]'::jsonb)
      INTO uids
    FROM (
      SELECT DISTINCT ON (real_name) id, real_name
      FROM users
      WHERE tenant_id::text = tid
        AND is_active = true
        AND real_name IN ({ROOM_SQL})
      ORDER BY real_name, created_at NULLS LAST
    ) x;

    -- 转新乡工艺包装
    SELECT COALESCE(jsonb_agg(id::text ORDER BY real_name), '[]'::jsonb)
      INTO pack_uids
    FROM (
      SELECT DISTINCT ON (real_name) id, real_name
      FROM users
      WHERE tenant_id::text = tid
        AND is_active = true
        AND real_name IN ({PACK_SQL})
      ORDER BY real_name, created_at NULLS LAST
    ) x;

    -- 科室：同名多条时优先技术总工/中央研究院路径
    SELECT COALESCE(jsonb_agg(id::text ORDER BY name), '[]'::jsonb)
      INTO dids
    FROM (
      SELECT DISTINCT ON (name) id, name
      FROM departments
      WHERE tenant_id::text = tid
        AND name IN ({OFFICE_SQL})
      ORDER BY name,
        CASE
          WHEN path LIKE '%中央研究院%' THEN 0
          WHEN path LIKE '%技术总工%' THEN 1
          ELSE 2
        END,
        length(coalesce(path, ''))
    ) x;

    UPDATE pickable_scopes
    SET name = '方案管理-设计指派',
        kind = 'person',
        description = '方案管理「设计指派」人选范围；在此直接勾选成员。',
        is_system = true,
        rules = jsonb_build_object(
          'role_codes', '[]'::jsonb,
          'user_ids', uids,
          'dept_ids', '[]'::jsonb,
          'include_children', true
        ),
        updated_at = NOW()
    WHERE tenant_id::text = tid AND code = 'room_leaders';

    UPDATE pickable_scopes
    SET name = '方案管理-科室',
        kind = 'department',
        description = '方案管理「科室」可选部门范围。',
        is_system = true,
        rules = jsonb_build_object(
          'role_codes', '[]'::jsonb,
          'user_ids', '[]'::jsonb,
          'dept_ids', dids,
          'include_children', true
        ),
        updated_at = NOW()
    WHERE tenant_id::text = tid AND code = 'scheme_offices';

    UPDATE pickable_scopes
    SET name = '方案管理-转新乡、工艺包装',
        kind = 'person',
        description = '方案管理「转新乡、工艺包装」人选范围；在此直接勾选成员。',
        is_system = true,
        rules = jsonb_build_object(
          'role_codes', '[]'::jsonb,
          'user_ids', pack_uids,
          'dept_ids', '[]'::jsonb,
          'include_children', true
        ),
        updated_at = NOW()
    WHERE tenant_id::text = tid AND code = 'fa-zxxgy';

    RAISE NOTICE 'tenant % room_leaders=% fa-zxxgy=% offices=%',
      tid, uids, pack_uids, dids;
  END LOOP;
END $$;

-- 方案/图纸已发布模板：transfer_packaging_users 挂上 fa-zxxgy
UPDATE lc_form_template_version v
SET field_definitions = (
  SELECT jsonb_agg(
    CASE
      WHEN (elem->>'id') = 'transfer_packaging_users' THEN
        jsonb_set(
          elem,
          '{{props}}',
          COALESCE(elem->'props', '{{}}'::jsonb) ||
            jsonb_build_object('pickable_scope', jsonb_build_object('scope_code', 'fa-zxxgy')),
          true
        )
      ELSE elem
    END
    ORDER BY ord
  )
  FROM jsonb_array_elements(v.field_definitions) WITH ORDINALITY AS t(elem, ord)
)
FROM lc_form_template t
WHERE v.template_id = t.id
  AND t.code IN ('scheme_management', 'drawing_requisition')
  AND v.status IN ('published', 'draft')
  AND EXISTS (
    SELECT 1 FROM jsonb_array_elements(v.field_definitions) e
    WHERE e->>'id' = 'transfer_packaging_users'
      AND COALESCE(e->'props'->'pickable_scope'->>'scope_code', '') IS DISTINCT FROM 'fa-zxxgy'
  );

SELECT s.tenant_id::text, s.code, s.name,
       jsonb_array_length(COALESCE(s.rules->'user_ids','[]'::jsonb)) AS n_users,
       jsonb_array_length(COALESCE(s.rules->'dept_ids','[]'::jsonb)) AS n_depts
FROM pickable_scopes s
ORDER BY s.tenant_id, s.code;
"""

VERIFY = f"""
-- room_leaders names
SELECT 'room_leaders' AS scope, u.real_name
FROM pickable_scopes s
CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'user_ids') AS uid
JOIN users u ON u.id::text = uid
WHERE s.code = 'room_leaders'
  AND s.tenant_id::text = '00000000-0000-0000-0000-000000000001'
ORDER BY u.real_name;

SELECT 'fa-zxxgy' AS scope, u.real_name
FROM pickable_scopes s
CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'user_ids') AS uid
JOIN users u ON u.id::text = uid
WHERE s.code = 'fa-zxxgy'
  AND s.tenant_id::text = '00000000-0000-0000-0000-000000000001'
ORDER BY u.real_name;

SELECT 'scheme_offices' AS scope, d.name, d.path
FROM pickable_scopes s
CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'dept_ids') AS did
JOIN departments d ON d.id::text = did
WHERE s.code = 'scheme_offices'
  AND s.tenant_id::text = '00000000-0000-0000-0000-000000000001'
ORDER BY d.name;

-- missing names?
SELECT 'MISSING room_leaders' AS tip, x.n
FROM (VALUES {", ".join("('" + n.replace("'", "''") + "')" for n in ROOM_LEADERS)}) AS x(n)
WHERE NOT EXISTS (
  SELECT 1
  FROM pickable_scopes s
  CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'user_ids') AS uid
  JOIN users u ON u.id::text = uid AND u.real_name = x.n
  WHERE s.code = 'room_leaders'
    AND s.tenant_id::text = '00000000-0000-0000-0000-000000000001'
);

SELECT 'MISSING fa-zxxgy' AS tip, x.n
FROM (VALUES {", ".join("('" + n.replace("'", "''") + "')" for n in TRANSFER_PACKAGING)}) AS x(n)
WHERE NOT EXISTS (
  SELECT 1
  FROM pickable_scopes s
  CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'user_ids') AS uid
  JOIN users u ON u.id::text = uid AND u.real_name = x.n
  WHERE s.code = 'fa-zxxgy'
    AND s.tenant_id::text = '00000000-0000-0000-0000-000000000001'
);

SELECT 'MISSING office' AS tip, x.n
FROM (VALUES {", ".join("('" + n.replace("'", "''") + "')" for n in SCHEME_OFFICES)}) AS x(n)
WHERE NOT EXISTS (
  SELECT 1
  FROM pickable_scopes s
  CROSS JOIN LATERAL jsonb_array_elements_text(s.rules->'dept_ids') AS did
  JOIN departments d ON d.id::text = did AND d.name = x.n
  WHERE s.code = 'scheme_offices'
    AND s.tenant_id::text = '00000000-0000-0000-0000-000000000001'
);
"""


def _write(c: paramiko.SSHClient, path: str, content: str) -> None:
    sftp = c.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(content)
    sftp.close()
    print("wrote", path, "bytes", len(content.encode("utf-8")))


def _run(c: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    print(">>>", cmd[:180])
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-5000:])
    if err.strip():
        print("ERR:", err.rstrip()[-2000:])
    print("[exit", code, "]")
    return out


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=25, look_for_keys=False, allow_agent=False)

    _write(c, "/tmp/_sync_pickable_local.sql", SQL)
    _run(
        c,
        "docker cp /tmp/_sync_pickable_local.sql spt-crm-db-1:/tmp/_sync_pickable_local.sql && "
        "docker exec -i spt-crm-db-1 psql -U postgres -d spt_crm -v ON_ERROR_STOP=1 -f /tmp/_sync_pickable_local.sql",
    )

    _write(c, "/tmp/_verify_pickable_local.sql", VERIFY)
    _run(
        c,
        "docker cp /tmp/_verify_pickable_local.sql spt-crm-db-1:/tmp/_verify_pickable_local.sql && "
        "docker exec -i spt-crm-db-1 psql -U postgres -d spt_crm -f /tmp/_verify_pickable_local.sql",
    )
    c.close()


if __name__ == "__main__":
    main()
