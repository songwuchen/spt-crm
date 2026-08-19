#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 192.168.1.205 拉取安装图设计通知单条数据到本地库。"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HOST = "192.168.1.205"
SSH_USER = "swc"
SSH_PWD = "Ruolin2025"
DEFAULT_SERIAL = "202608184192"
DEFAULT_TENANT = "00000000-0000-0000-0000-000000000001"
DUMP_PATH = ROOT.parent / f"_pull_install_{DEFAULT_SERIAL}.json"

REMOTE_EXPORT_PY = r'''
import asyncio, json, sys
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import text
from app.database import async_session_factory

SERIAL = "{serial}"


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, UUID):
        return str(o)
    raise TypeError(type(o))


async def fetch_rows(db, sql, params=None):
    rows = (await db.execute(text(sql), params or {})).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, (datetime, date, Decimal, UUID)):
                d[k] = _json_default(v)
        out.append(d)
    return out


async def main():
    async with async_session_factory() as db:
        fi_rows = await fetch_rows(db, """
            SELECT fi.*, t.code AS template_code
            FROM lc_form_instance fi
            JOIN lc_form_template t ON t.id = fi.template_id
            WHERE fi.is_deleted = false
              AND t.code = 'install_drawing_notice'
              AND (fi.business_no = :s OR fi.form_data->>'serial_no' = :s)
            ORDER BY fi.created_at DESC
            LIMIT 1
        """, {"s": SERIAL})
        if not fi_rows:
            print(json.dumps({"error": f"not found: {SERIAL}"}, ensure_ascii=False))
            return
        fi = fi_rows[0]
        fid = fi["id"]
        tenant_id = fi["tenant_id"]
        detail_rows = await fetch_rows(db, """
            SELECT * FROM lc_form_instance_detail_row
            WHERE form_instance_id = :fid ORDER BY field_key, row_index
        """, {"fid": fid})

        wis = await fetch_rows(db, """
            SELECT * FROM wf_process_instance
            WHERE form_instance_id = :fid ORDER BY created_at
        """, {"fid": fid})
        if not wis:
            wis = await fetch_rows(db, """
                SELECT * FROM wf_process_instance
                WHERE business_no = :s OR title ILIKE :pat
                ORDER BY created_at DESC LIMIT 1
            """, {"s": SERIAL, "pat": f"%{SERIAL}%"})

        wf_bundle = []
        for wi in wis:
            pid = wi["id"]
            wf_bundle.append({
                "process_instance": wi,
                "node_instances": await fetch_rows(db, """
                    SELECT * FROM wf_node_instance WHERE process_instance_id = :p
                    ORDER BY started_at NULLS LAST, created_at
                """, {"p": pid}),
                "task_instances": await fetch_rows(db, """
                    SELECT * FROM wf_task_instance WHERE process_instance_id = :p
                    ORDER BY task_order, created_at
                """, {"p": pid}),
                "action_logs": await fetch_rows(db, """
                    SELECT * FROM wf_task_action_log WHERE process_instance_id = :p
                    ORDER BY created_at
                """, {"p": pid}),
                "comments": await fetch_rows(db, """
                    SELECT * FROM wf_process_comment WHERE process_instance_id = :p
                    ORDER BY created_at
                """, {"p": pid}),
                "cc_records": await fetch_rows(db, """
                    SELECT * FROM wf_process_cc WHERE process_instance_id = :p
                    ORDER BY created_at
                """, {"p": pid}),
            })

        user_ids = set()
        for key in ("initiator_id", "created_by", "deleted_by"):
            if fi.get(key):
                user_ids.add(fi[key])
        for wb in wf_bundle:
            wi = wb["process_instance"]
            for key in ("initiator_id",):
                if wi.get(key):
                    user_ids.add(wi[key])
            for t in wb["task_instances"]:
                if t.get("assignee_id"):
                    user_ids.add(t["assignee_id"])
            for l in wb["action_logs"]:
                if l.get("actor_id"):
                    user_ids.add(l["actor_id"])
            for c in wb["comments"]:
                if c.get("user_id"):
                    user_ids.add(c["user_id"])
            for c in wb["cc_records"]:
                if c.get("user_id"):
                    user_ids.add(c["user_id"])

        users = []
        if user_ids:
            users = await fetch_rows(db, """
                SELECT id, username, real_name, tenant_id
                FROM users WHERE id = ANY(:ids)
            """, {"ids": list(user_ids)})

        ver_ids = {wi["process_version_id"] for wi in wis if wi.get("process_version_id")}
        versions = []
        if ver_ids:
            versions = await fetch_rows(db, """
                SELECT * FROM wf_process_definition_version WHERE id = ANY(:ids)
            """, {"ids": list(ver_ids)})

        pd_ids = {wi["process_definition_id"] for wi in wis if wi.get("process_definition_id")}
        definitions = []
        if pd_ids:
            definitions = await fetch_rows(db, """
                SELECT id, tenant_id, name, code, form_template_id, current_version, status
                FROM wf_process_definition WHERE id = ANY(:ids)
            """, {"ids": list(pd_ids)})

        tpl_ver = None
        if fi.get("template_version_id"):
            tv = await fetch_rows(db, """
                SELECT id, template_id, version_number, status FROM lc_form_template_version
                WHERE id = :id
            """, {"id": fi["template_version_id"]})
            tpl_ver = tv[0] if tv else None

        out = {
            "serial": SERIAL,
            "tenant_id": tenant_id,
            "form_instance": fi,
            "form_detail_rows": detail_rows,
            "template_version": tpl_ver,
            "workflow_definitions": definitions,
            "workflow_versions": versions,
            "workflows": wf_bundle,
            "users": users,
        }
        print(json.dumps(out, ensure_ascii=False, default=_json_default))

asyncio.run(main())
'''


def export_from_205(serial: str) -> dict:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=SSH_USER, password=SSH_PWD, timeout=30, look_for_keys=False, allow_agent=False)
    py = REMOTE_EXPORT_PY.replace("{serial}", serial)
    b64 = base64.b64encode(py.encode("utf-8")).decode("ascii")
    cmd = (
        f"echo {SSH_PWD} | sudo -S docker exec -i spt-crm-backend-1 sh -c "
        f"\"echo {b64} | base64 -d > /tmp/_pull_install.py && PYTHONPATH=/app python /tmp/_pull_install.py\""
    )
    _, o, e = c.exec_command(cmd, timeout=300)
    out = o.read().decode("utf-8", "replace").strip()
    err = e.read().decode("utf-8", "replace").strip()
    code = o.channel.recv_exit_status()
    c.close()
    if code != 0:
        raise RuntimeError(f"205 export failed exit={code}\n{out}\n{err}")
    if not out:
        raise RuntimeError(f"205 export empty\nstderr: {err}")
    data = json.loads(out.splitlines()[-1] if out.count("{") > 1 else out)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data


DT_KEYS = (
    "created_at", "updated_at", "deleted_at",
    "started_at", "completed_at", "action_at", "sla_deadline",
)


def parse_dt(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    s = str(v)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return v


def normalize_row(row: dict) -> dict:
    out = dict(row)
    for k in DT_KEYS:
        if k in out:
            out[k] = parse_dt(out[k])
    for k in ("nominated_approvers", "pending_joins"):
        if out.get(k) == "null":
            out[k] = None
    return out


async def resolve_local_user(db, remote_user: dict, tenant_id: str) -> str | None:
    from sqlalchemy import select, text

    from app.domains.auth.models import User

    rid = remote_user.get("id")
    uname = (remote_user.get("username") or "").strip()
    rname = (remote_user.get("real_name") or "").strip()
    if uname:
        u = (await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == uname)
        )).scalar_one_or_none()
        if u:
            return u.id
    if rname:
        u = (await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.real_name == rname)
        )).scalar_one_or_none()
        if u:
            return u.id
    if rid:
        u = (await db.execute(
            select(User).where(User.id == rid, User.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if u:
            return rid
    return None


async def import_to_local(data: dict, tenant_id: str) -> None:
    from sqlalchemy import delete, select, text

    from app.database import async_session_factory
    import app.domains.organization.models  # noqa: F401
    from app.domains.auth.models import User  # noqa: F401
    from app.domains.lowcode.models import FormInstance, FormTemplate
    from app.domains.lowcode.workflow_models import (
        WfNodeInstance,
        WfProcessDefinition,
        WfProcessDefinitionVersion,
        WfProcessInstance,
        WfProcessCc,
        WfProcessComment,
        WfTaskActionLog,
        WfTaskInstance,
    )

    serial = data.get("serial") or data["form_instance"].get("business_no")
    fi_remote = data["form_instance"]

    async with async_session_factory() as db:
        tpl = (await db.execute(
            select(FormTemplate).where(
                FormTemplate.tenant_id == tenant_id,
                FormTemplate.code == "install_drawing_notice",
                FormTemplate.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not tpl:
            raise RuntimeError("本地未安装 install_drawing_notice，请先 ensure 内置表单")

        from app.domains.lowcode.service import get_published_version
        from app.domains.lowcode.workflow_service import _published_version

        pub_tpl_ver = await get_published_version(db, tenant_id, tpl.id)

        wf_def = (await db.execute(
            select(WfProcessDefinition).where(
                WfProcessDefinition.tenant_id == tenant_id,
                WfProcessDefinition.form_template_id == tpl.id,
                WfProcessDefinition.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not wf_def:
            raise RuntimeError("本地未找到 install_drawing_notice 绑定流程")

        wf_pub_ver = await _published_version(db, tenant_id, wf_def.id)
        if not wf_pub_ver:
            raise RuntimeError("本地流程无已发布版本")

        user_map: dict[str, str] = {}
        admin = (await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == "admin")
        )).scalar_one_or_none()
        admin_id = admin.id if admin else None
        for ru in data.get("users") or []:
            lid = await resolve_local_user(db, ru, tenant_id)
            if lid:
                user_map[ru["id"]] = lid
        fallback_user = admin_id or next(iter(user_map.values()), None)
        if not fallback_user:
            raise RuntimeError("本地找不到可映射用户，请确认 admin 或对应人员已同步")

        def map_uid(uid: str | None) -> str | None:
            if not uid:
                return uid
            return user_map.get(uid, fallback_user)

        # 删除本地同流水号旧数据
        old_fis = (await db.execute(text("""
            SELECT id FROM lc_form_instance
            WHERE tenant_id = :t AND is_deleted = false
              AND (business_no = :s OR form_data->>'serial_no' = :s)
        """), {"t": tenant_id, "s": serial})).scalars().all()
        for old_id in old_fis:
            old_pids = (await db.execute(text(
                "SELECT id FROM wf_process_instance WHERE form_instance_id = :fid"
            ), {"fid": old_id})).scalars().all()
            for pid in old_pids:
                await db.execute(delete(WfTaskActionLog).where(
                    WfTaskActionLog.process_instance_id == pid))
                await db.execute(delete(WfProcessComment).where(
                    WfProcessComment.process_instance_id == pid))
                await db.execute(delete(WfProcessCc).where(
                    WfProcessCc.process_instance_id == pid))
                await db.execute(delete(WfTaskInstance).where(
                    WfTaskInstance.process_instance_id == pid))
                await db.execute(delete(WfNodeInstance).where(
                    WfNodeInstance.process_instance_id == pid))
                await db.execute(delete(WfProcessInstance).where(
                    WfProcessInstance.id == pid))
            await db.execute(text(
                "DELETE FROM lc_form_instance_detail_row WHERE form_instance_id = :fid"
            ), {"fid": old_id})
            await db.execute(delete(FormInstance).where(FormInstance.id == old_id))

        # 插入表单实例（保留原 id）
        fi_payload = dict(fi_remote)
        fi_id = fi_payload["id"]
        fi_payload["tenant_id"] = tenant_id
        fi_payload["template_id"] = tpl.id
        fi_payload["template_version_id"] = pub_tpl_ver.id
        fi_payload["initiator_id"] = map_uid(fi_payload.get("initiator_id"))
        fi_payload["created_by"] = map_uid(fi_payload.get("created_by"))
        fi_payload.pop("template_code", None)
        fi_payload = normalize_row(fi_payload)
        db.add(FormInstance(**fi_payload))

        for dr in data.get("form_detail_rows") or []:
            row = normalize_row(dict(dr))
            row["tenant_id"] = tenant_id
            row["form_instance_id"] = fi_id
            await db.execute(text("""
                INSERT INTO lc_form_instance_detail_row
                (id, tenant_id, form_instance_id, field_key, row_index, row_data, created_at, updated_at)
                VALUES (:id, :tenant_id, :form_instance_id, :field_key, :row_index, :row_data, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """), row)

        for wb in data.get("workflows") or []:
            wi = normalize_row(dict(wb["process_instance"]))
            pid = wi["id"]
            wi["tenant_id"] = tenant_id
            wi["form_instance_id"] = fi_id
            wi["process_definition_id"] = wf_def.id
            wi["process_version_id"] = wf_pub_ver.id
            wi["initiator_id"] = map_uid(wi.get("initiator_id"))
            wi["initiator_dept_id"] = wi.get("initiator_dept_id")
            db.add(WfProcessInstance(**wi))

            ni_id_map: dict[str, str] = {}
            for ni in wb.get("node_instances") or []:
                row = normalize_row(dict(ni))
                nid = row["id"]
                ni_id_map[nid] = nid
                row["tenant_id"] = tenant_id
                row["process_instance_id"] = pid
                db.add(WfNodeInstance(**row))

            for ti in wb.get("task_instances") or []:
                row = normalize_row(dict(ti))
                row["tenant_id"] = tenant_id
                row["process_instance_id"] = pid
                row["node_instance_id"] = ni_id_map.get(row.get("node_instance_id"), row.get("node_instance_id"))
                row["assignee_id"] = map_uid(row.get("assignee_id"))
                db.add(WfTaskInstance(**row))

            for lg in wb.get("action_logs") or []:
                row = normalize_row(dict(lg))
                row["tenant_id"] = tenant_id
                row["process_instance_id"] = pid
                row["actor_id"] = map_uid(row.get("actor_id"))
                db.add(WfTaskActionLog(**row))

            for cm in wb.get("comments") or []:
                row = normalize_row(dict(cm))
                row["tenant_id"] = tenant_id
                row["process_instance_id"] = pid
                row["user_id"] = map_uid(row.get("user_id"))
                db.add(WfProcessComment(**row))

            for cc in wb.get("cc_records") or []:
                row = normalize_row(dict(cc))
                row["tenant_id"] = tenant_id
                row["process_instance_id"] = pid
                row["user_id"] = map_uid(row.get("user_id"))
                db.add(WfProcessCc(**row))

        await db.execute(text(
            "UPDATE lc_form_instance SET process_instance_id = :pid WHERE id = :fid"
        ), {"pid": data["workflows"][-1]["process_instance"]["id"] if data.get("workflows") else None, "fid": fi_id})

        await db.commit()
        print(f"imported serial={serial} form_instance={fi_id} tenant={tenant_id}")
        print(f"user_map={json.dumps(user_map, ensure_ascii=False)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=DEFAULT_SERIAL)
    ap.add_argument("--tenant", default=DEFAULT_TENANT)
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--import-file", type=str, default="")
    args = ap.parse_args()

    dump = Path(str(ROOT.parent / f"_pull_install_{args.serial}.json"))
    if args.import_file:
        data = json.loads(Path(args.import_file).read_text(encoding="utf-8"))
    else:
        print(f"exporting {args.serial} from {HOST} ...")
        data = export_from_205(args.serial)
        dump.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved {dump}")
        if args.export_only:
            return

    asyncio.run(import_to_local(data, args.tenant))


if __name__ == "__main__":
    main()
