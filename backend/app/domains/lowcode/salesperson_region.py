# -*- coding: utf-8 -*-
"""业务员 → 区域经理/组长对照表（对齐简道云销售中心联动基础表）。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid

logger = logging.getLogger("spt_crm.lowcode.salesperson_region")

SALESPERSON_REGION_FORM = "salesperson_region_map"
_DUMP_NAME = "_jdy_salesperson_region_map_data.json"


def _dump_path() -> Path:
    """兼容本地 `backend/app/...` 与容器 `/app/app/...` 布局。"""
    here = Path(__file__).resolve()
    for i in range(2, 7):
        if i >= len(here.parents):
            break
        cand = here.parents[i] / "docs" / "product" / _DUMP_NAME
        if cand.exists():
            return cand
    return here.parents[min(4, len(here.parents) - 1)] / "docs" / "product" / _DUMP_NAME


# 简道云字段
_JDY_SP_USER = "_widget_1770082739661"       # 业务员（成员）
_JDY_SP_UNAME = "_widget_1770082739660"      # 员工ID（username 文本）
_JDY_RM_USER = "_widget_1705115573567"       # 大区经理或组长（成员）
_JDY_REGION = "_widget_1705115573566"        # 区域


def _person_id(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("id") or "").strip()
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            return str(first.get("id") or "").strip()
        return str(first or "").strip()
    return str(raw or "").strip()


def _jdy_user(raw: Any) -> tuple[str, str]:
    """返回 (username, name)。"""
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if not isinstance(raw, dict):
        return "", ""
    uname = str(raw.get("username") or "").strip()
    name = str(raw.get("name") or "").strip()
    return uname, name


def _norm_name(s: str) -> str:
    """去掉括号备注后的姓名，便于「王宇（y）」↔「王宇」匹配。"""
    import re
    t = str(s or "").strip()
    if not t:
        return ""
    t = re.sub(r"[（(][^）)]*[）)]", "", t).strip()
    return t


def load_jdy_salesperson_region_items() -> list[dict[str, str]]:
    """从简道云 dump 解析对照行。"""
    docs = _dump_path()
    if not docs.exists():
        logger.warning("salesperson region dump missing: %s", docs)
        return []
    try:
        payload = json.loads(docs.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("salesperson region dump read fail: %s", e)
        return []
    rows = []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            rows = data.get("items") or data.get("data") or []
        elif isinstance(data, list):
            rows = data
        else:
            rows = payload.get("items") or []
    elif isinstance(payload, list):
        rows = payload

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        sp_uname, sp_name = _jdy_user(r.get(_JDY_SP_USER))
        if not sp_uname:
            sp_uname = str(r.get(_JDY_SP_UNAME) or "").strip()
        rm_uname, rm_name = _jdy_user(r.get(_JDY_RM_USER))
        region = str(r.get(_JDY_REGION) or "").strip()
        if not sp_uname or not rm_uname:
            continue
        if sp_uname in seen:
            continue
        seen.add(sp_uname)
        out.append({
            "salesperson_username": sp_uname,
            "salesperson_name": sp_name,
            "region_manager_username": rm_uname,
            "region_manager_name": rm_name,
            "region": region,
        })
    return out


async def resolve_region_manager(
    db: AsyncSession,
    tenant_id: str,
    salesperson_id: str | None,
    user: dict | None = None,
) -> dict[str, str | None]:
    """按业务员用户 id 查对照表；无匹配返回空 id/name。

    提交路径不做 ensure_builtin，基础表未初始化时返回空，由管理端 ensure 补种。
    """
    sid = str(salesperson_id or "").strip()
    empty: dict[str, str | None] = {
        "salesperson_id": sid or None,
        "region_manager_id": None,
        "region_manager_name": None,
    }
    if not sid:
        return empty

    from app.domains.lowcode.models import FormTemplate

    tpl_id = (await db.execute(
        select(FormTemplate.id).where(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.code == SALESPERSON_REGION_FORM,
            FormTemplate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not tpl_id:
        return empty

    row = (await db.execute(
        text(
            """
            SELECT form_data->'region_manager' AS rm
            FROM lc_form_instance
            WHERE tenant_id = :t
              AND template_id = :tpl
              AND is_deleted = false
              AND status <> 'draft'
              AND (
                form_data->>'salesperson' = :sid
                OR form_data->'salesperson'->>'id' = :sid
                OR form_data->'salesperson'->>0 = :sid
                OR form_data->'salesperson'->0->>'id' = :sid
              )
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"t": tenant_id, "tpl": tpl_id, "sid": sid},
    )).first()
    if not row:
        return empty

    rm_id = _person_id(row[0])
    if not rm_id:
        return empty

    name = (await db.execute(
        text(
            """
            SELECT COALESCE(NULLIF(TRIM(real_name), ''), username)
            FROM users
            WHERE id = :uid AND tenant_id = :t
            LIMIT 1
            """
        ),
        {"uid": rm_id, "t": tenant_id},
    )).scalar_one_or_none()

    return {
        "salesperson_id": sid,
        "region_manager_id": rm_id,
        "region_manager_name": (str(name).strip() if name else None) or None,
    }


async def seed_salesperson_region_if_empty(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    user: dict,
) -> int:
    """基础表无数据时，从简道云 dump 按 username 幂等灌入。返回新增条数。"""
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

    items = load_jdy_salesperson_region_items()
    if not items:
        return 0

    users = (
        await db.execute(
            text(
                """
                SELECT id, username, real_name
                FROM users
                WHERE tenant_id = :t AND COALESCE(is_active, true) = true
                """
            ),
            {"t": tenant_id},
        )
    ).all()
    by_username: dict[str, str] = {}
    by_name: dict[str, str] = {}
    by_norm_name: dict[str, str] = {}
    for u in users:
        uid, uname, rname = str(u[0]), str(u[1] or "").strip(), str(u[2] or "").strip()
        if uname and uname not in by_username:
            by_username[uname] = uid
        if rname and rname not in by_name:
            by_name[rname] = uid
        nn = _norm_name(rname)
        if nn and nn not in by_norm_name:
            by_norm_name[nn] = uid

    published = await lc_svc.get_published_version(db, tenant_id, template_id)
    if not published:
        return 0
    field_defs = published.field_definitions or []
    user_id = str(user.get("sub") or "") or "00000000-0000-0000-0000-000000000000"

    added = 0
    skipped = 0
    for it in items:
        sp_id = (
            by_username.get(it["salesperson_username"])
            or by_name.get(it["salesperson_name"])
            or by_norm_name.get(_norm_name(it["salesperson_name"]))
        )
        rm_id = (
            by_username.get(it["region_manager_username"])
            or by_name.get(it["region_manager_name"])
            or by_norm_name.get(_norm_name(it["region_manager_name"]))
        )
        if not sp_id or not rm_id:
            skipped += 1
            logger.info(
                "salesperson region seed skip sp=%s(%s) rm=%s(%s)",
                it["salesperson_name"], it["salesperson_username"],
                it["region_manager_name"], it["region_manager_username"],
            )
            continue
        sp_label = it["salesperson_name"] or it["salesperson_username"]
        rm_label = it["region_manager_name"] or it["region_manager_username"]
        region = it.get("region") or ""
        title = f"{sp_label} → {rm_label}" + (f" · {region}" if region else "")
        form_data: dict[str, Any] = {
            "salesperson": sp_id,
            "region_manager": rm_id,
        }
        if region:
            form_data["region"] = region
        db.add(
            FormInstance(
                id=generate_uuid(),
                tenant_id=tenant_id,
                template_id=template_id,
                template_version_id=published.id,
                title=title,
                status="submitted",
                form_data=form_data,
                field_definitions=field_defs,
                created_by=user_id,
                initiator_id=user_id,
            )
        )
        added += 1
    if added:
        await db.flush()
        logger.info(
            "salesperson region seed tenant=%s added=%s skipped=%s",
            tenant_id[:8], added, skipped,
        )
    elif skipped:
        logger.warning(
            "salesperson region seed tenant=%s matched=0 skipped=%s (check username sync)",
            tenant_id[:8], skipped,
        )
    return added
