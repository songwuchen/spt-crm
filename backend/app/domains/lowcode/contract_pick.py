# -*- coding: utf-8 -*-
"""合同关联选择弹窗（对齐简道云 linkfield 列表）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contract.models import Contract

# 发货通知等：合同号选择弹窗列（对齐简道云 linkFieldsFormShow）
CONTRACT_PICK_COLUMNS: list[tuple[str, str]] = [
    ("change_status", "合同状态"),
    ("drawing_no", "图纸编号"),
    ("customer_name", "收货单位"),
    ("department_name", "部门"),
]


def contract_pick_column_defs() -> list[dict[str, str]]:
    return [{"key": k, "title": t} for k, t in CONTRACT_PICK_COLUMNS]


def _change_status_label(change_type: str | None) -> str:
    raw = (change_type or "").strip().lower()
    if raw in ("new", "新增"):
        return "新增"
    if raw in ("change", "变动"):
        return "变动"
    return change_type or ""


def contract_pick_label(*, drawing_no: str | None, contract_no: str | None, cid: str) -> str:
    draw = (drawing_no or "").strip()
    no = (contract_no or "").strip()
    if draw and no and draw != no:
        return f"{draw}（{no}）"
    return draw or no or cid


async def list_pickable_contracts_page(
    db: AsyncSession,
    tenant_id: str,
    *,
    keyword: str | None = None,
    ids: list[str] | None = None,
    department_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页合同选择列表（登录即可，不要求 contract:view）。"""
    columns = contract_pick_column_defs()
    empty: dict[str, Any] = {
        "items": [], "total": 0, "page": page, "page_size": page_size, "columns": columns,
    }
    conds = [Contract.tenant_id == tenant_id]
    dept = (department_id or "").strip()
    if dept:
        conds.append(Contract.department_id == dept)

    id_list = [x for x in (ids or []) if x]
    if id_list:
        conds.append(Contract.id.in_(id_list))
        total = len(id_list)
        page, page_size = 1, max(len(id_list), 1)
    else:
        kw = (keyword or "").strip()
        if kw:
            like = f"%{kw}%"
            conds.append(or_(
                Contract.drawing_no.ilike(like),
                Contract.contract_no.ilike(like),
                Contract.peer_contract_no.ilike(like),
            ))
        total = int((await db.execute(
            select(func.count()).select_from(Contract).where(*conds)
        )).scalar_one() or 0)
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 50))

    order = [
        case((Contract.drawing_no.is_not(None) & (Contract.drawing_no != ""), 0), else_=1),
        Contract.updated_at.desc(),
    ]
    kw = (keyword or "").strip()
    if kw and not id_list:
        like = f"%{kw}%"
        order = [
            case(
                (Contract.drawing_no.ilike(like), 0),
                (Contract.contract_no.ilike(like), 1),
                else_=2,
            ),
            Contract.updated_at.desc(),
        ]

    q = (
        select(Contract)
        .where(*conds)
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await db.execute(q)).scalars().all())

    project_ids = [c.project_id for c in rows if c.project_id and not c.customer_id]
    project_customer: dict[str, str] = {}
    if project_ids:
        from app.domains.project.models import OpportunityProject
        prows = (await db.execute(
            select(OpportunityProject.id, OpportunityProject.customer_id).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.id.in_(list(dict.fromkeys(project_ids))),
            )
        )).all()
        for pid, cust_id in prows:
            if cust_id:
                project_customer[str(pid)] = str(cust_id)

    cust_ids: list[str] = []
    for c in rows:
        if c.customer_id:
            cust_ids.append(str(c.customer_id))
        elif c.project_id and str(c.project_id) in project_customer:
            cust_ids.append(project_customer[str(c.project_id)])

    customer_names: dict[str, str] = {}
    if cust_ids:
        from app.common.list_enrich import customer_names_map
        customer_names = await customer_names_map(db, tenant_id, list(dict.fromkeys(cust_ids)))

    items: list[dict[str, Any]] = []
    for c in rows:
        cust_id = str(c.customer_id) if c.customer_id else None
        if not cust_id and c.project_id:
            cust_id = project_customer.get(str(c.project_id))
        customer_name = customer_names.get(cust_id, "") if cust_id else ""
        if not customer_name and c.registration_json and isinstance(c.registration_json, dict):
            customer_name = str(c.registration_json.get("customer_name") or "").strip()

        cols = {
            "change_status": _change_status_label(c.change_type),
            "drawing_no": (c.drawing_no or "").strip(),
            "customer_name": customer_name,
            "department_name": (c.department_name or "").strip(),
        }
        items.append({
            "id": c.id,
            "contract_no": c.contract_no,
            "drawing_no": c.drawing_no,
            "label": contract_pick_label(
                drawing_no=c.drawing_no, contract_no=c.contract_no, cid=c.id,
            ),
            "cols": cols,
        })

    return {
        "items": items,
        "total": total if not id_list else len(items),
        "page": page,
        "page_size": page_size,
        "columns": columns,
    }
