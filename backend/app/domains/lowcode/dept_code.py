# -*- coding: utf-8 -*-
"""部门编号基础表：选部门后回填部门编号（对齐简道云「部门编号基础表」）。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid

logger = logging.getLogger("spt_crm.lowcode.dept_code")

DEPARTMENT_CODE_FORM = "department_code_base"
_DOCS = Path(__file__).resolve().parents[4] / "docs" / "product" / "_jdy_dept_code_base.json"

DESIGN_CARD_SERIAL_RULES: list[dict[str, Any]] = [
    {"type": "field", "field_id": "dept_code"},
    {"type": "text", "value": "-"},
    {"type": "date", "format": "yyyyMMdd", "date_field": "apply_datetime"},
    {
        "type": "counter",
        "digits": 2,
        "fixed": True,
        "initial_value": 1,
        "reset_period": "daily",
        "date_field": "apply_datetime",
        "period_scope_field": "dept_code",
    },
]


def normalize_dept_name(name: str | None) -> str:
    s = (name or "").strip()
    return (
        s.replace("(", "（")
        .replace(")", "）")
        .replace(" ", "")
        .replace("\u3000", "")
    )


def load_jdy_dept_code_items() -> list[dict[str, str]]:
    if not _DOCS.exists():
        return []
    raw = json.loads(_DOCS.read_text(encoding="utf-8"))
    items = raw.get("items") if isinstance(raw, dict) else []
    out: list[dict[str, str]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        code = str(it.get("code") or "").strip()
        name = str(it.get("dept_name") or "").strip()
        if code and name:
            out.append({"code": code, "dept_name": name})
    return out


async def resolve_dept_code(
    db: AsyncSession,
    tenant_id: str,
    department_id: str | None,
    user: dict | None = None,
) -> str | None:
    """按部门 id 查基础表中的部门编号；无匹配返回 None。

    提交路径禁止 ensure_builtin / 全表扫 FormInstance（会拖慢审批提交）。
    基础表未初始化时返回 None，由管理端或 ensure 接口补种。
    """
    dept_id = str(department_id or "").strip()
    if not dept_id:
        return None
    from app.domains.lowcode.models import FormTemplate

    tpl_id = (await db.execute(
        select(FormTemplate.id).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.code == DEPARTMENT_CODE_FORM,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not tpl_id:
        return None

    # PostgreSQL JSONB 定点查询：department 可能是 id 字符串或 {id:...}
    row = (await db.execute(
        text(
            """
            SELECT form_data->>'dept_code' AS code
            FROM lc_form_instance
            WHERE tenant_id = :t
              AND template_id = :tpl
              AND is_deleted = false
              AND status <> 'draft'
              AND COALESCE(form_data->>'dept_code', '') <> ''
              AND (
                form_data->>'department' = :dept
                OR form_data->'department'->>'id' = :dept
              )
            LIMIT 1
            """
        ),
        {"t": tenant_id, "tpl": tpl_id, "dept": dept_id},
    )).first()
    if row and row[0]:
        return str(row[0]).strip() or None
    return None


async def fill_dept_code_in_form_data(
    db: AsyncSession,
    tenant_id: str,
    form_data: dict[str, Any],
    field_defs: list[dict[str, Any]] | None,
    user: dict | None = None,
) -> dict[str, Any]:
    """若表单含 department + dept_code，且部门编号为空，则按基础表回填。"""
    ids = {str(f.get("id")) for f in (field_defs or []) if isinstance(f, dict) and f.get("id")}
    if "department" not in ids or "dept_code" not in ids:
        return form_data
    if str(form_data.get("dept_code") or "").strip():
        return form_data
    raw = form_data.get("department")
    if isinstance(raw, dict):
        dept_id = str(raw.get("id") or "").strip()
    elif isinstance(raw, list) and raw:
        first = raw[0]
        dept_id = str(first.get("id") if isinstance(first, dict) else first or "").strip()
    else:
        dept_id = str(raw or "").strip()
    code = await resolve_dept_code(db, tenant_id, dept_id, user)
    if code:
        form_data["dept_code"] = code
    return form_data


async def seed_department_codes_if_empty(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    user: dict,
) -> int:
    """基础表无数据时，从简道云 dump 按部门名幂等灌入。返回新增条数。"""
    from app.domains.lowcode.models import FormInstance
    from app.domains.lowcode import service as lc_svc

    existing = (
        await db.execute(
            select(FormInstance.id).where(
                FormInstance.tenant_id == tenant_id,
                FormInstance.template_id == template_id,
                FormInstance.is_deleted == False,  # noqa: E712
            ).limit(1)
        )
    ).first()
    if existing:
        return 0

    items = load_jdy_dept_code_items()
    if not items:
        return 0

    depts = (
        await db.execute(
            text("SELECT id, name FROM departments WHERE tenant_id = :t"),
            {"t": tenant_id},
        )
    ).all()
    by_name: dict[str, str] = {}
    for d in depts:
        key = normalize_dept_name(d[1])
        if key and key not in by_name:
            by_name[key] = str(d[0])

    published = await lc_svc.get_published_version(db, tenant_id, template_id)
    if not published:
        return 0
    field_defs = published.field_definitions or []
    user_id = str(user.get("sub") or "") or "00000000-0000-0000-0000-000000000000"

    added = 0
    for it in items:
        dept_id = by_name.get(normalize_dept_name(it["dept_name"]))
        if not dept_id:
            logger.info("dept code seed skip unmatched name=%s", it["dept_name"])
            continue
        code = it["code"]
        title = f"{code} · {it['dept_name']}"
        db.add(
            FormInstance(
                id=generate_uuid(),
                tenant_id=tenant_id,
                template_id=template_id,
                template_version_id=published.id,
                title=title,
                status="submitted",
                form_data={"department": dept_id, "dept_code": code},
                field_definitions=field_defs,
                created_by=user_id,
                initiator_id=user_id,
            )
        )
        added += 1
    if added:
        await db.flush()
        logger.info("dept code seed tenant=%s added=%s", tenant_id[:8], added)
    return added


def apply_design_card_serial_rules(field_defs: list[dict[str, Any]]) -> None:
    """把 design_card_no 改为 auto_number，规则：部门编号-yyyyMMdd-两位日序（按部门编号分序列）。"""
    for fd in field_defs or []:
        if not isinstance(fd, dict) or fd.get("id") != "design_card_no":
            continue
        fd["type"] = "auto_number"
        props = dict(fd.get("props") or {}) if isinstance(fd.get("props"), dict) else {}
        props["serial_rules"] = [dict(r) for r in DESIGN_CARD_SERIAL_RULES]
        fd["props"] = props
        fd.setdefault("available_on_create", True)
        fd.setdefault("fill_stage", "initiator")
