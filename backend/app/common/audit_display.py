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
        for diff in changes.values():
            if not isinstance(diff, dict):
                continue
            for side in ("old", "new"):
                raw = diff.get(side)
                if _is_empty(raw):
                    continue
                disp = diff.get(f"display_{side}")
                if not disp:
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

    person_ids: set[str] = set()
    dept_ids: set[str] = set()
    contract_ids: set[str] = set()

    for key, diff in changes.items():
        fid = key.split(".")[-1]
        ftype = type_map.get(fid, "")
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
                    # 字段类型未知或多人数组：按人员 UUID 尝试解析
                    person_ids.add(i)

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
        ftype = type_map.get(fid, "")
        opts = opt_map.get(fid, {})
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
