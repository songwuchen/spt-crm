"""数据日志展示增强：字段值解析为可读文本（对齐简道云数据日志）。"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _field_type_map(field_defs: list[dict[str, Any]] | None) -> dict[str, str]:
    if not field_defs:
        return {}
    return {
        str(f.get("id")): str(f.get("type") or "")
        for f in field_defs if isinstance(f, dict) and f.get("id")
    }


def _option_label_map(field_defs: list[dict[str, Any]] | None) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for f in field_defs or []:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        fid = str(f["id"])
        opts = f.get("options") or []
        if not isinstance(opts, list):
            continue
        m: dict[str, str] = {}
        for o in opts:
            if isinstance(o, dict):
                val = o.get("value")
                lab = o.get("label") or val
                if val is not None:
                    m[str(val)] = str(lab)
            elif o is not None:
                m[str(o)] = str(o)
        if m:
            out[fid] = m
    return out


def _collect_ids(val: Any) -> list[str]:
    if val is None or val == "":
        return []
    if isinstance(val, list):
        out: list[str] = []
        for x in val:
            out.extend(_collect_ids(x))
        return out
    if isinstance(val, dict):
        rid = val.get("id")
        return [str(rid)] if rid else []
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        if s.startswith("[") or s.startswith("{"):
            try:
                import json
                parsed = json.loads(s)
                if parsed is not val:
                    return _collect_ids(parsed)
            except Exception:
                pass
        return [s]
    s = str(val).strip()
    return [s] if s else []


def _is_empty(val: Any) -> bool:
    return val is None or val == "" or val == [] or val == {}


def _field_def_map(field_defs: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not field_defs:
        return {}
    return {
        str(f.get("id")): f
        for f in field_defs if isinstance(f, dict) and f.get("id")
    }


def _column_option_maps(field_def: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not field_def:
        return out
    for col in field_def.get("detail_table_columns") or []:
        if not isinstance(col, dict) or not col.get("id"):
            continue
        cid = str(col["id"])
        opts = col.get("options") or []
        if not isinstance(opts, list):
            continue
        m: dict[str, str] = {}
        for o in opts:
            if isinstance(o, dict):
                val = o.get("value")
                lab = o.get("label") or val
                if val is not None:
                    m[str(val)] = str(lab)
            elif o is not None:
                m[str(o)] = str(o)
        if m:
            out[cid] = m
    return out


def _format_cell_value(
    val: Any,
    col_def: dict[str, Any],
    labels: dict[str, str],
    opt_map: dict[str, dict[str, str]],
) -> str | None:
    cid = str(col_def.get("id") or "")
    ctype = str(col_def.get("type") or "")
    return _format_display_value(val, ctype, labels, opt_map.get(cid, {}))


def _format_detail_table_rows(
    rows: Any,
    field_def: dict[str, Any] | None,
    labels: dict[str, str],
    col_opt_map: dict[str, dict[str, str]],
) -> str | None:
    if _is_empty(rows):
        return None
    if not isinstance(rows, list):
        return _format_display_value(rows, "detail_table", labels, {})
    cols = [
        c for c in (field_def or {}).get("detail_table_columns") or []
        if isinstance(c, dict) and c.get("id")
    ]
    if not cols:
        parts: list[str] = []
        for i, row in enumerate(rows, 1):
            if isinstance(row, dict):
                vals = [
                    str(v).strip() for v in row.values()
                    if v not in (None, "") and str(v).strip()
                ]
                if vals:
                    parts.append(f"第{i}行：" + "，".join(vals[:6]))
            elif not _is_empty(row):
                parts.append(f"第{i}行：{row}")
        return "；".join(parts) if parts else f"{len(rows)} 行"

    lines: list[str] = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        cells: list[str] = []
        for col in cols:
            cid = str(col["id"])
            raw = row.get(cid)
            if _is_empty(raw):
                continue
            lab = str(col.get("label") or cid)
            val = _format_cell_value(raw, col, labels, col_opt_map) or "—"
            cells.append(f"{lab} {val}")
        if cells:
            lines.append(f"第{i}行：" + "，".join(cells))
    return "；".join(lines) if lines else f"{len(rows)} 行"


def _cell_values_equal(a: Any, b: Any) -> bool:
    from app.common.audit_diff import serialize_value
    return serialize_value(a) == serialize_value(b)


def _compute_detail_table_diff(
    old: Any,
    new: Any,
    field_def: dict[str, Any] | None,
    labels: dict[str, str],
    col_opt_map: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    old_rows = old if isinstance(old, list) else []
    new_rows = new if isinstance(new, list) else []
    cols = [
        c for c in (field_def or {}).get("detail_table_columns") or []
        if isinstance(c, dict) and c.get("id")
    ]
    if not cols:
        return None

    max_len = max(len(old_rows), len(new_rows))
    rows_out: list[dict[str, Any]] = []
    for idx in range(max_len):
        orow = old_rows[idx] if idx < len(old_rows) else {}
        nrow = new_rows[idx] if idx < len(new_rows) else {}
        if not isinstance(orow, dict):
            orow = {}
        if not isinstance(nrow, dict):
            nrow = {}
        cells: list[dict[str, Any]] = []
        row_changed = False
        for col in cols:
            cid = str(col["id"])
            ov, nv = orow.get(cid), nrow.get(cid)
            if _is_empty(ov) and _is_empty(nv):
                continue
            changed = not _cell_values_equal(ov, nv)
            if changed:
                row_changed = True
            disp_old = None if _is_empty(ov) else _format_cell_value(ov, col, labels, col_opt_map)
            disp_new = None if _is_empty(nv) else _format_cell_value(nv, col, labels, col_opt_map)
            cells.append({
                "col_id": cid,
                "label": str(col.get("label") or cid),
                "old": disp_old,
                "new": disp_new,
                "changed": changed,
            })
        if cells and (row_changed or idx >= len(old_rows) or idx >= len(new_rows)):
            rows_out.append({"index": idx + 1, "cells": cells})

    if not rows_out:
        return None
    return {
        "columns": [
            {"id": str(c["id"]), "label": str(c.get("label") or c["id"])}
            for c in cols
        ],
        "rows": rows_out,
    }


def _collect_ids_from_detail_table(val: Any, field_def: dict[str, Any] | None) -> tuple[set[str], set[str]]:
    person_ids: set[str] = set()
    dept_ids: set[str] = set()
    if not isinstance(val, list) or not field_def:
        return person_ids, dept_ids
    cols = field_def.get("detail_table_columns") or []
    for row in val:
        if not isinstance(row, dict):
            continue
        for col in cols:
            if not isinstance(col, dict):
                continue
            cid = str(col.get("id") or "")
            ctype = str(col.get("type") or "")
            cell = row.get(cid)
            for i in _collect_ids(cell):
                if not _UUID_RE.match(i):
                    continue
                if ctype in ("person", "person_multi", "user"):
                    person_ids.add(i)
                elif ctype in ("department", "department_multi"):
                    dept_ids.add(i)
                else:
                    person_ids.add(i)
    return person_ids, dept_ids


async def hydrate_audit_log_detail(
    db: AsyncSession,
    tenant_id: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """读取数据日志时补全 display_*（兼容旧日志未写入展示值）。"""
    if not detail or not isinstance(detail, dict):
        return detail
    changes = detail.get("changes")
    if not isinstance(changes, dict) or not changes:
        return detail

    def _needs_hydrate() -> bool:
        for key, diff in changes.items():
            if not isinstance(diff, dict):
                continue
            if diff.get("detail_table_diff"):
                continue
            raw_new = diff.get("new")
            raw_old = diff.get("old")
            if isinstance(raw_new, list) or isinstance(raw_old, list):
                if not diff.get("display_new") and not _is_empty(raw_new):
                    return True
                if not diff.get("display_old") and not _is_empty(raw_old):
                    return True
            for side in ("old", "new"):
                raw = diff.get(side)
                if _is_empty(raw):
                    continue
                disp = diff.get(f"display_{side}")
                if not disp:
                    return True
                if isinstance(disp, (list, dict)):
                    return True
                if isinstance(raw, (list, dict)) and "[object Object]" in str(disp):
                    return True
                ids = _collect_ids(raw)
                if ids and all(_UUID_RE.match(i) for i in ids):
                    disp_s = str(disp)
                    if disp_s == str(raw) or disp_s.startswith("["):
                        return True
        return False

    if not _needs_hydrate():
        return detail

    field_defs: list[dict[str, Any]] | None = None
    if resource_type == "form_instance":
        from app.domains.lowcode.models import FormInstance
        fi = await db.get(FormInstance, resource_id)
        if fi and fi.tenant_id == tenant_id:
            field_defs = list(fi.field_definitions or [])
            if not field_defs and fi.template_id:
                from app.domains.lowcode.service import get_published_version
                try:
                    pub = await get_published_version(db, tenant_id, fi.template_id)
                    if pub:
                        field_defs = list(pub.field_definitions or [])
                except Exception:
                    pass
    elif resource_type == "wf_process_instance":
        from app.domains.lowcode.workflow_models import WfProcessInstance
        from app.domains.lowcode.models import FormInstance
        inst = await db.get(WfProcessInstance, resource_id)
        if inst and inst.form_instance_id:
            fi = await db.get(FormInstance, inst.form_instance_id)
            if fi:
                field_defs = list(fi.field_definitions or [])

    enriched = await enrich_form_changes_for_display(db, tenant_id, changes, field_defs)
    return {**detail, "changes": enriched}


def filter_create_log_changes(changes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """创建日志：简道云通常只展示流水号；否则保留有值的新增字段。"""
    if not changes:
        return {}
    if "serial_no" in changes and not _is_empty(changes["serial_no"].get("new")):
        return {"serial_no": changes["serial_no"]}
    out: dict[str, dict[str, Any]] = {}
    for key, diff in changes.items():
        if _is_empty(diff.get("new")):
            continue
        out[key] = diff
    return out


async def enrich_form_changes_for_display(
    db: AsyncSession,
    tenant_id: str,
    changes: dict[str, dict[str, Any]],
    field_defs: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """为 diff 附加 display_old / display_new（人员姓名、合同号、选项文案等）。"""
    if not changes:
        return changes

    type_map = _field_type_map(field_defs)
    opt_map = _option_label_map(field_defs)
    field_map = _field_def_map(field_defs)

    person_ids: set[str] = set()
    dept_ids: set[str] = set()
    contract_ids: set[str] = set()

    for key, diff in changes.items():
        fid = key.split(".")[-1]
        fdef = field_map.get(fid, {})
        ftype = type_map.get(fid, "") or str(fdef.get("type") or "")
        for side in ("old", "new"):
            val = diff.get(side)
            ids = _collect_ids(val)
            for i in ids:
                if not _UUID_RE.match(i):
                    continue
                if ftype in ("person", "person_multi", "user"):
                    person_ids.add(i)
                elif ftype in ("department", "department_multi"):
                    dept_ids.add(i)
                elif ftype == "contract":
                    contract_ids.add(i)
                elif isinstance(val, list) or ftype == "":
                    person_ids.add(i)
            if ftype in ("detail_table", "sub_table_data"):
                p2, d2 = _collect_ids_from_detail_table(val, fdef)
                person_ids |= p2
                dept_ids |= d2

    labels: dict[str, str] = {}
    if person_ids:
        from app.domains.auth.models import User
        rows = (await db.execute(
            select(User.id, User.real_name, User.username).where(
                User.tenant_id == tenant_id,
                User.id.in_(person_ids),
            )
        )).all()
        for uid, real_name, username in rows:
            labels[str(uid)] = (real_name or username or str(uid)).strip()

    if dept_ids:
        from app.domains.organization.models import Department
        rows = (await db.execute(
            select(Department.id, Department.name).where(
                Department.tenant_id == tenant_id,
                Department.id.in_(dept_ids),
            )
        )).all()
        for did, name in rows:
            if name:
                labels[str(did)] = str(name).strip()

    if contract_ids:
        from app.domains.contract.models import Contract
        rows = (await db.execute(
            select(Contract.id, Contract.contract_no, Contract.drawing_no).where(
                Contract.tenant_id == tenant_id,
                Contract.id.in_(contract_ids),
            )
        )).all()
        for cid, cno, dno in rows:
            labels[str(cid)] = (str(dno or cno or cid)).strip()

    enriched: dict[str, dict[str, Any]] = {}
    for key, diff in changes.items():
        entry = dict(diff)
        fid = key.split(".")[-1]
        fdef = field_map.get(fid, {})
        ftype = type_map.get(fid, "") or str(fdef.get("type") or "")
        opts = opt_map.get(fid, {})
        col_opt_map = _column_option_maps(fdef)
        if ftype in ("detail_table", "sub_table_data"):
            entry["display_old"] = _format_detail_table_rows(
                diff.get("old"), fdef, labels, col_opt_map,
            )
            entry["display_new"] = _format_detail_table_rows(
                diff.get("new"), fdef, labels, col_opt_map,
            )
            dt_diff = _compute_detail_table_diff(
                diff.get("old"), diff.get("new"), fdef, labels, col_opt_map,
            )
            if dt_diff:
                entry["detail_table_diff"] = dt_diff
        else:
            for side in ("old", "new"):
                val = diff.get(side)
                entry[f"display_{side}"] = _format_display_value(val, ftype, labels, opts)
        enriched[key] = entry
    return enriched


def _format_display_value(
    val: Any,
    ftype: str,
    labels: dict[str, str],
    opts: dict[str, str],
) -> str | None:
    if _is_empty(val):
        return None
    if ftype in ("person", "user"):
        ids = _collect_ids(val)
        if ids and _UUID_RE.match(ids[0]):
            return labels.get(ids[0]) or ids[0]
        return str(val)
    if ftype == "person_multi":
        parts = []
        for i in _collect_ids(val):
            parts.append(labels.get(i, i) if _UUID_RE.match(i) else i)
        joined = "、".join(p for p in parts if p)
        return joined or str(val)
    if ftype in ("department", "department_multi"):
        parts = []
        for i in _collect_ids(val):
            parts.append(labels.get(i, i) if _UUID_RE.match(i) else i)
        joined = "、".join(p for p in parts if p)
        return joined or str(val)
    if ftype == "contract":
        ids = _collect_ids(val)
        if ids and _UUID_RE.match(ids[0]):
            return labels.get(ids[0]) or ids[0]
        return str(val)
    if ftype in ("select", "radio", "checkbox") and opts:
        if isinstance(val, list):
            return "、".join(opts.get(str(v), str(v)) for v in val)
        return opts.get(str(val), str(val))
    # 未知类型但值为 UUID / UUID 列表 → 用已解析的姓名/名称
    ids = _collect_ids(val)
    if ids and all(_UUID_RE.match(i) for i in ids):
        parts = [labels.get(i) or i for i in ids]
        if any(labels.get(i) for i in ids):
            return "、".join(parts)
        # 未解析到姓名时也避免输出 JSON 数组字符串
        if len(parts) == 1:
            return parts[0]
        return "、".join(parts)
    if isinstance(val, (list, dict)):
        try:
            import json
            return json.dumps(val, ensure_ascii=False)
        except Exception:
            return str(val)
    return str(val)
