# -*- coding: utf-8 -*-
"""合同关联选择弹窗（对齐简道云 linkfield 列表）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contract.models import Contract
from app.domains.lowcode.contract_pick_scope import (
    apply_contract_department_filter,
    resolve_pick_department_ids,
)

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
    department_ids: list[str] | None = None,
    scope_all: bool = False,
    user_department_ids: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页合同选择列表（登录即可，不要求 contract:view）。"""
    columns = contract_pick_column_defs()
    id_list = [x for x in (ids or []) if x]
    pick_depts = resolve_pick_department_ids(
        scope_all=scope_all,
        user_department_ids=user_department_ids,
        department_id=department_id,
        department_ids=department_ids,
        for_id_lookup=bool(id_list),
    )
    if pick_depts:
        from app.common.dept_equivalence import expand_equivalent_department_ids
        pick_depts = await expand_equivalent_department_ids(db, tenant_id, pick_depts)
    conds = [Contract.tenant_id == tenant_id]
    apply_contract_department_filter(conds, Contract, pick_depts)
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


def _scalar_person_ref(raw: Any) -> tuple[str | None, str | None]:
    """从 registration_json 等位置解析 person 字段（uuid / 姓名 / {id,name}）。"""
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, dict):
        pid = raw.get("id") or raw.get("value") or raw.get("user_id")
        pname = raw.get("name") or raw.get("label") or raw.get("real_name")
        return (
            str(pid).strip() if pid not in (None, "") else None,
            str(pname).strip() if pname not in (None, "") else None,
        )
    if isinstance(raw, list) and raw:
        return _scalar_person_ref(raw[0])
    text = str(raw).strip()
    if not text:
        return None, None
    # uuid 形态
    if len(text) == 36 and text.count("-") == 4:
        return text, None
    return None, text


async def resolve_contract_assignee_id(
    db: AsyncSession,
    tenant_id: str,
    contract: Contract,
) -> str | None:
    """选合同带出业务员：列 assignee_id 优先，否则按姓名/登记 JSON 反查用户。"""
    from app.domains.auth.models import User as AuthUser
    from app.domains.openapi.service import resolve_owner_id

    raw_id = (contract.assignee_id or "").strip()
    if raw_id:
        exists = (await db.execute(
            select(AuthUser.id).where(
                AuthUser.id == raw_id,
                AuthUser.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if exists:
            return raw_id

    reg = contract.registration_json if isinstance(contract.registration_json, dict) else {}
    candidates: list[tuple[str | None, str | None]] = []
    for id_key, name_key in (
        ("assignee_id", "assignee_name"),
        ("owner_id", "owner_name"),
        ("sales_person", None),
        ("salesperson", None),
        ("业务人员", None),
        ("业务员", None),
    ):
        rid, rname = _scalar_person_ref(reg.get(id_key))
        if name_key:
            _, n2 = _scalar_person_ref(reg.get(name_key))
            rname = rname or n2
        elif rid is None and rname is None:
            rid, rname = _scalar_person_ref(reg.get(id_key))
        candidates.append((rid, rname))
    candidates.append((None, (contract.assignee_name or "").strip() or None))

    for owner_id, owner_name in candidates:
        uid = await resolve_owner_id(
            db, tenant_id, owner_id=owner_id, owner_name=owner_name,
        )
        if uid:
            return uid
    return None


async def resolve_contract_sales_person_ref(
    db: AsyncSession,
    tenant_id: str,
    contract: Contract,
) -> str | None:
    """选合同带出业务员：优先 CRM 用户 id；无法匹配时回落姓名字符串（只读人员字段可展示）。"""
    uid = await resolve_contract_assignee_id(db, tenant_id, contract)
    if uid:
        return uid
    name = (contract.assignee_name or "").strip()
    if name:
        return name
    reg = contract.registration_json if isinstance(contract.registration_json, dict) else {}
    for key in ("assignee_name", "owner_name", "sales_person", "salesperson", "业务人员", "业务员"):
        _, rname = _scalar_person_ref(reg.get(key))
        if rname:
            return rname
    return None
