# -*- coding: utf-8 -*-
"""商机关联的低代码单据：方案/图纸、报价管理等。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# template_code, form_data 关联字段, 展示用类型名
# scheme_management 仅保留历史合并单据；新建走 drawing_requisition / install_drawing_notice / presale_service_notice
_SCHEME_SPECS: list[tuple[str, str, str]] = [
    ("scheme_management", "related_project", "方案管理"),
    ("install_drawing_notice", "project_no", "安装图设计通知"),
]

_QUOTE_SPECS: list[tuple[str, str, str]] = [
    ("quote_management", "related_project", "报价管理"),
]

_SCHEME_TYPE_LABELS = {
    "requisition": "领图",
    "install": "安装图·投标",
}

_INST_STATUS_LABELS = {
    "draft": "草稿",
    "submitted": "已提交",
    "running": "审批中",
    "completed": "已通过",
    "rejected": "已驳回",
    "withdrawn": "已撤回",
}


def _txt(fd: dict | None, key: str) -> str | None:
    if not isinstance(fd, dict):
        return None
    raw = fd.get(key)
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    return s or None


def _scheme_subtype_label(code: str, fd: dict | None) -> str | None:
    if code != "scheme_management" or not isinstance(fd, dict):
        return None
    st = _txt(fd, "scheme_type")
    return _SCHEME_TYPE_LABELS.get(st or "", st)


def _row_from_instance(inst, *, template_code: str, template_name: str) -> dict[str, Any]:
    fd = inst.form_data if isinstance(inst.form_data, dict) else {}
    serial = _txt(fd, "serial_no") or getattr(inst, "business_no", None) or inst.title
    subtype = _scheme_subtype_label(template_code, fd)
    kind_label = template_name
    if subtype:
        kind_label = f"{template_name} · {subtype}"
    status = inst.status or "draft"
    row: dict[str, Any] = {
        "id": inst.id,
        "template_code": template_code,
        "template_name": template_name,
        "kind_label": kind_label,
        "subtype": _txt(fd, "scheme_type"),
        "subtype_label": subtype,
        "serial_no": serial,
        "business_no": getattr(inst, "business_no", None) or serial,
        "design_card_no": _txt(fd, "design_card_no"),
        "customer_name": _txt(fd, "customer_name"),
        "matter": _txt(fd, "matter"),
        "contract_no": _txt(fd, "contract_no") or _txt(fd, "ref_contract_no") or _txt(fd, "card_contract_no"),
        "ref_contract_no": _txt(fd, "ref_contract_no"),
        "price_type": _txt(fd, "price_type"),
        "customer_category": _txt(fd, "customer_category"),
        "need_purchase": _txt(fd, "need_purchase"),
        "apply_datetime": _txt(fd, "apply_datetime"),
        "status": status,
        "status_label": _INST_STATUS_LABELS.get(status, status),
        "initiator_id": inst.initiator_id,
        "created_at": inst.created_at.isoformat() if inst.created_at else "",
    }
    return row


async def _list_project_forms(
    db: AsyncSession,
    tenant_id: str,
    project_id: str,
    specs: list[tuple[str, str, str]],
    *,
    user: dict | None,
    owner_ids: list[str] | None,
    limit_per_template: int = 100,
) -> list[dict[str, Any]]:
    from app.domains.lowcode.service import get_template_by_code, list_instances, user_display_names

    rows: list[dict[str, Any]] = []
    initiator_ids: list[str] = []

    for code, link_field, display_name in specs:
        tpl = await get_template_by_code(db, tenant_id, code)
        if not tpl:
            continue
        filters = json.dumps({
            "match": "all",
            "rules": [{"field": link_field, "op": "eq", "value": project_id}],
        }, ensure_ascii=False)
        items, _total = await list_instances(
            db, tenant_id, tpl.id, 1, limit_per_template,
            filters=filters, user=user, owner_ids=owner_ids,
        )
        for inst in items:
            rows.append(_row_from_instance(inst, template_code=code, template_name=display_name))
            if inst.initiator_id:
                initiator_ids.append(inst.initiator_id)

    if initiator_ids and rows:
        name_map = await user_display_names(db, tenant_id, initiator_ids)
        for row in rows:
            iid = row.get("initiator_id")
            if iid and name_map.get(iid):
                row["initiator_name"] = name_map[iid]

    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


async def list_project_scheme_forms(
    db: AsyncSession,
    tenant_id: str,
    project_id: str,
    *,
    user: dict | None,
    owner_ids: list[str] | None,
    limit_per_template: int = 100,
) -> list[dict[str, Any]]:
    return await _list_project_forms(
        db, tenant_id, project_id, _SCHEME_SPECS,
        user=user, owner_ids=owner_ids, limit_per_template=limit_per_template,
    )


async def list_project_quote_forms(
    db: AsyncSession,
    tenant_id: str,
    project_id: str,
    *,
    user: dict | None,
    owner_ids: list[str] | None,
    limit_per_template: int = 100,
) -> list[dict[str, Any]]:
    return await _list_project_forms(
        db, tenant_id, project_id, _QUOTE_SPECS,
        user=user, owner_ids=owner_ids, limit_per_template=limit_per_template,
    )
