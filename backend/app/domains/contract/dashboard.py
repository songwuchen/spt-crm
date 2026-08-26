"""合同管理仪表盘 — 对齐简道云「合同管理仪表盘」聚合口径。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contract.models import Contract
from app.domains.customer.models import Customer
from app.domains.project.models import OpportunityProject


def _customer_display_name_empty():
    """登记 JSON / 直连客户均为空。"""
    reg_name = Contract.registration_json["customer_name"].as_string()
    return and_(
        Contract.customer_id.is_(None),
        or_(reg_name.is_(None), reg_name == ""),
    )


def _customer_display_name_not_empty():
    return or_(
        Contract.customer_id.isnot(None),
        and_(
            Contract.registration_json["customer_name"].as_string().isnot(None),
            Contract.registration_json["customer_name"].as_string() != "",
        ),
    )


def _customer_name_match(tenant_id: str, kw: str, *, mode: str):
    """单值客户名匹配（eq / ne / contains / not_contains）。"""
    mode = (mode or "contains").lower()
    if not kw:
        return None
    if mode in ("eq", "ne"):
        matching = select(Customer.id).where(
            Customer.tenant_id == tenant_id,
            func.lower(Customer.name) == kw.lower(),
        )
        via_direct = Contract.customer_id.in_(matching)
        via_project = Contract.project_id.in_(
            select(OpportunityProject.id).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.customer_id.in_(matching),
            )
        )
        via_reg = func.lower(Contract.registration_json["customer_name"].as_string()) == kw.lower()
        clause = or_(via_direct, via_project, via_reg)
        return ~clause if mode == "ne" else clause
    like = f"%{kw}%"
    matching = select(Customer.id).where(
        Customer.tenant_id == tenant_id,
        Customer.name.ilike(like),
    )
    via_direct = Contract.customer_id.in_(matching)
    via_project = Contract.project_id.in_(
        select(OpportunityProject.id).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.customer_id.in_(matching),
        )
    )
    via_reg = Contract.registration_json["customer_name"].as_string().ilike(like)
    clause = or_(via_direct, via_project, via_reg)
    return ~clause if mode == "not_contains" else clause


def _customer_filter_clause(
    tenant_id: str,
    *,
    customer_op: str | None,
    customer_name: str | None,
    customer_names: str | None,
    customer_match: str | None = None,
):
    op = (customer_op or "").lower()
    if not op and customer_match:
        op = "eq" if customer_match.lower() == "eq" else "contains"
    if not op:
        op = "contains"

    if op == "is_empty":
        return _customer_display_name_empty()
    if op == "is_not_empty":
        return _customer_display_name_not_empty()

    if op in ("in", "nin"):
        names = [x.strip() for x in (customer_names or customer_name or "").split(",") if x.strip()]
        if not names:
            return None
        parts = [_customer_name_match(tenant_id, n, mode="eq") for n in names]
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        clause = or_(*parts)
        return ~clause if op == "nin" else clause

    kw = (customer_name or "").strip()
    if not kw:
        return None
    mode = op if op in ("eq", "ne", "contains", "not_contains") else "contains"
    return _customer_name_match(tenant_id, kw, mode=mode)


def _dept_empty_clause():
    return or_(Contract.department_id.is_(None), Contract.department_id == "")


def _department_filter_clause(
    department_id: str | None,
    department_ids: str | None,
    *,
    department_op: str | None = None,
):
    op = (department_op or "in").lower()
    if op == "is_empty":
        return _dept_empty_clause()
    if op == "is_not_empty":
        return ~_dept_empty_clause()

    ids: list[str] = []
    if department_ids:
        ids = [x.strip() for x in department_ids.split(",") if x.strip()]
    elif department_id:
        ids = [department_id.strip()]
    if not ids:
        return None

    empty_marker = "__empty__"
    has_empty = empty_marker in ids
    real_ids = [x for x in ids if x != empty_marker]

    def _in_real():
        if not real_ids:
            return None
        if len(real_ids) == 1:
            return Contract.department_id == real_ids[0]
        return Contract.department_id.in_(real_ids)

    def _match_in():
        parts: list = []
        r = _in_real()
        if r is not None:
            parts.append(r)
        if has_empty:
            parts.append(_dept_empty_clause())
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return or_(*parts)

    if op == "eq":
        clause = _match_in()
        return clause
    if op == "in":
        return _match_in()
    if op == "ne":
        clause = _match_in()
        return ~clause if clause is not None else None
    if op == "nin":
        clause = _match_in()
        return ~clause if clause is not None else None
    return _match_in()


def _assignee_filter_clause(
    assignee_id: str | None,
    assignee_ids: str | None,
    *,
    assignee_op: str | None = None,
):
    op = (assignee_op or "eq").lower()
    if op == "is_empty":
        return or_(Contract.assignee_id.is_(None), Contract.assignee_id == "")
    if op == "is_not_empty":
        return and_(Contract.assignee_id.isnot(None), Contract.assignee_id != "")

    ids: list[str] = []
    if assignee_ids:
        ids = [x.strip() for x in assignee_ids.split(",") if x.strip()]
    elif assignee_id:
        ids = [assignee_id.strip()]
    if not ids:
        return None

    if op in ("eq", "in"):
        if len(ids) == 1:
            return Contract.assignee_id == ids[0]
        return Contract.assignee_id.in_(ids)
    if op in ("ne", "nin"):
        if len(ids) == 1:
            return or_(Contract.assignee_id.is_(None), Contract.assignee_id != ids[0])
        return or_(Contract.assignee_id.is_(None), ~Contract.assignee_id.in_(ids))
    return Contract.assignee_id == ids[0] if len(ids) == 1 else Contract.assignee_id.in_(ids)


def _card_date_filter_clause(
    *,
    card_date_op: str | None,
    card_from: date | None,
    card_to: date | None,
    card_date: date | None,
):
    op = (card_date_op or "preset").lower()
    if op == "is_empty":
        return Contract.card_date.is_(None)
    if op == "is_not_empty":
        return Contract.card_date.isnot(None)
    if op == "eq" and card_date:
        return Contract.card_date == card_date
    if op == "ne" and card_date:
        return or_(Contract.card_date.is_(None), Contract.card_date != card_date)
    if op == "gte" and card_date:
        return Contract.card_date >= card_date
    if op == "lte" and card_date:
        return Contract.card_date <= card_date
    parts: list = []
    if card_from:
        parts.append(Contract.card_date >= card_from)
    if card_to:
        parts.append(Contract.card_date <= card_to)
    if not parts:
        return None
    return and_(*parts) if len(parts) > 1 else parts[0]


def _customer_industry_label():
    return func.coalesce(
        Customer.industry_l1,
        Customer.industry,
        Customer.smart_industry_category,
        literal("未填写"),
    )


def _customer_province_label():
    return func.coalesce(Customer.province, literal("未知"))


async def _scoped_customer_ids(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    *,
    customer_name: str | None,
    created_from: date | None = None,
    created_to: date | None = None,
):
    """公司客户子集（简道云默认 is_company_customer=是），含客户数据权限。"""
    from app.common.data_scope import apply_data_scope

    conds: list = [
        Customer.tenant_id == tenant_id,
        Customer.is_deleted == False,  # noqa: E712
        Customer.is_company_customer == True,  # noqa: E712
    ]
    kw = (customer_name or "").strip()
    if kw:
        conds.append(Customer.name.ilike(f"%{kw}%"))
    if created_from:
        conds.append(func.date(Customer.created_at) >= created_from)
    if created_to:
        conds.append(func.date(Customer.created_at) <= created_to)

    q = select(Customer.id).where(*conds)
    q = await apply_data_scope(q, db, tenant_id, user, Customer, "customer")
    return q.subquery()


async def _customer_dashboard_stats(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    *,
    customer_name: str | None,
    card_from: date | None,
    card_to: date | None,
) -> dict[str, Any]:
    scoped = await _scoped_customer_ids(
        db, tenant_id, user, customer_name=customer_name,
    )
    base = [Customer.id.in_(select(scoped.c.id))]

    def _count_stmt(label_expr, *, order_desc: bool = True, limit: int | None = None):
        labeled = label_expr.label("label")
        stmt = (
            select(labeled, func.count(Customer.id).label("count"))
            .where(*base)
            .group_by(labeled)
            .order_by(func.count(Customer.id).desc() if order_desc else func.count(Customer.id).asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return stmt

    total = (await db.execute(
        select(func.count(Customer.id)).where(*base)
    )).scalar() or 0

    cutoff_year = date.today().year - 10
    founded_over_10y = (await db.execute(
        select(func.count(Customer.id)).where(
            *base,
            Customer.founded_year.isnot(None),
            Customer.founded_year <= cutoff_year,
        )
    )).scalar() or 0

    industry_rows = (await db.execute(_count_stmt(_customer_industry_label()))).all()
    nature_rows = (await db.execute(
        _count_stmt(func.coalesce(Customer.customer_nature, literal("未填写")))
    )).all()
    province_rows = (await db.execute(_count_stmt(_customer_province_label()))).all()

    # 客户地图：简道云 additionally binds 下卡日期 → 客户 createTime
    map_scoped = await _scoped_customer_ids(
        db, tenant_id, user,
        customer_name=customer_name,
        created_from=card_from,
        created_to=card_to,
    )
    map_base = [Customer.id.in_(select(map_scoped.c.id))]
    prov_label = _customer_province_label().label("label")
    map_rows = (await db.execute(
        select(
            prov_label,
            func.count(Customer.id).label("count"),
        )
        .where(*map_base)
        .group_by(prov_label)
        .order_by(func.count(Customer.id).desc())
    )).all()

    def _pack_count(rows) -> list[dict[str, Any]]:
        return [
            {"label": str(r.label or "未知"), "count": int(r.count or 0), "amount": 0.0}
            for r in rows
        ]

    return {
        "total_count": int(total),
        "founded_over_10y_count": int(founded_over_10y),
        "by_industry": _pack_count(industry_rows),
        "by_nature": _pack_count(nature_rows),
        "by_province": _pack_count(province_rows),
        "map_by_province": _pack_count(map_rows),
    }


async def _contract_industry_amount(
    db: AsyncSession,
    tenant_id: str,
    base: list,
) -> list[dict[str, Any]]:
    """行业合同额：合同 registration_json.industry，回落客户行业。"""
    industry_label = func.coalesce(
        Contract.registration_json["industry"].as_string(),
        Customer.industry_l1,
        Customer.industry,
        literal("未分类"),
    ).label("label")
    rows = (await db.execute(
        select(
            industry_label,
            func.count(Contract.id).label("count"),
            func.coalesce(func.sum(Contract.amount_total), 0).label("amount"),
        )
        .select_from(Contract)
        .outerjoin(Customer, and_(Customer.id == Contract.customer_id, Customer.tenant_id == tenant_id))
        .where(*base)
        .group_by(industry_label)
        .order_by(func.coalesce(func.sum(Contract.amount_total), 0).desc())
    )).all()
    return [
        {"label": str(r.label or "未分类"), "count": int(r.count or 0), "amount": float(r.amount or 0)}
        for r in rows
    ]


async def _dept_month_stats(db: AsyncSession, base: list) -> list[dict[str, Any]]:
    """合同数量和金额表：下卡月 × 部门 → 数量/金额/平均。"""
    month_l = func.coalesce(func.to_char(Contract.card_date, "YYYY-MM"), literal("未知")).label("month")
    dept_l = func.coalesce(Contract.department_name, literal("未填写")).label("department")
    rows = (await db.execute(
        select(
            month_l,
            dept_l,
            func.count(Contract.id).label("count"),
            func.coalesce(func.sum(Contract.amount_total), 0).label("amount"),
        )
        .where(*base)
        .group_by(month_l, dept_l)
        .order_by(month_l.desc(), dept_l)
    )).all()
    out: list[dict[str, Any]] = []
    for r in rows:
        cnt = int(r.count or 0)
        amt = float(r.amount or 0)
        out.append({
            "month": str(r.month or "未知"),
            "department": str(r.department or "未填写"),
            "count": cnt,
            "amount": amt,
            "avg_amount": (amt / cnt) if cnt else 0.0,
        })
    return out


async def _dept_workload_stats(db: AsyncSession, base: list) -> list[dict[str, Any]]:
    """部门工作量统计：下卡月 × 部门 × 工作量 → 合同金额。"""
    month_l = func.coalesce(func.to_char(Contract.card_date, "YYYY-MM"), literal("未知")).label("month")
    dept_l = func.coalesce(Contract.department_name, literal("未填写")).label("department")
    workload_l = func.coalesce(Contract.registration_json["workload"].as_string(), literal("未填写")).label("workload")
    rows = (await db.execute(
        select(
            month_l, dept_l, workload_l,
            func.count(Contract.id).label("count"),
            func.coalesce(func.sum(Contract.amount_total), 0).label("amount"),
        )
        .where(*base)
        .group_by(month_l, dept_l, workload_l)
        .order_by(month_l, dept_l, workload_l)
    )).all()
    return [
        {
            "month": str(r.month or "未知"),
            "department": str(r.department or "未填写"),
            "workload": str(r.workload or "未填写"),
            "count": int(r.count or 0),
            "amount": float(r.amount or 0),
        }
        for r in rows
    ]


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


async def _scoped_contract_ids(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    *,
    customer_name: str | None,
    customer_names: str | None = None,
    customer_op: str | None = None,
    customer_match: str | None = None,
    card_date_op: str | None = None,
    card_from: date | None,
    card_to: date | None,
    card_date: date | None = None,
    department_id: str | None,
    department_ids: str | None = None,
    department_op: str | None = None,
    assignee_id: str | None,
    assignee_ids: str | None = None,
    assignee_op: str | None = None,
):
    from app.common.data_scope import apply_project_child_scope

    conds: list = [Contract.tenant_id == tenant_id]

    card_clause = _card_date_filter_clause(
        card_date_op=card_date_op,
        card_from=card_from,
        card_to=card_to,
        card_date=card_date,
    )
    if card_clause is not None:
        conds.append(card_clause)

    dept = _department_filter_clause(
        department_id, department_ids, department_op=department_op,
    )
    if dept is not None:
        conds.append(dept)

    assignee = _assignee_filter_clause(
        assignee_id, assignee_ids, assignee_op=assignee_op,
    )
    if assignee is not None:
        conds.append(assignee)

    cust = _customer_filter_clause(
        tenant_id,
        customer_op=customer_op,
        customer_name=customer_name,
        customer_names=customer_names,
        customer_match=customer_match,
    )
    if cust is not None:
        conds.append(cust)

    q = select(Contract.id).where(*conds)
    cq = select(func.count(Contract.id)).where(*conds)
    q, _cq = await apply_project_child_scope(
        q, cq, db, tenant_id, user, Contract, biz_type="contract",
    )
    return q.subquery()


async def contract_dashboard_summary(
    db: AsyncSession,
    tenant_id: str,
    user: dict,
    *,
    customer_name: str | None = None,
    customer_names: str | None = None,
    customer_op: str | None = None,
    customer_match: str | None = None,
    card_date_op: str | None = None,
    card_date: str | None = None,
    card_date_from: str | None = None,
    card_date_to: str | None = None,
    department_id: str | None = None,
    department_ids: str | None = None,
    department_op: str | None = None,
    assignee_id: str | None = None,
    assignee_ids: str | None = None,
    assignee_op: str | None = None,
) -> dict[str, Any]:
    card_op = (card_date_op or "preset").lower()
    card_from = _parse_date(card_date_from)
    card_to = _parse_date(card_date_to)
    card_d = _parse_date(card_date)
    if card_op not in ("is_empty", "is_not_empty", "eq", "ne", "gte", "lte"):
        if card_from is None and card_to is None:
            today = date.today()
            card_from = date(today.year, 1, 1)
            card_to = date(today.year, 12, 31)

    scoped = await _scoped_contract_ids(
        db, tenant_id, user,
        customer_name=customer_name,
        customer_names=customer_names,
        customer_op=customer_op,
        customer_match=customer_match,
        card_date_op=card_date_op,
        card_from=card_from,
        card_to=card_to,
        card_date=card_d,
        department_id=department_id,
        department_ids=department_ids,
        department_op=department_op,
        assignee_id=assignee_id,
        assignee_ids=assignee_ids,
        assignee_op=assignee_op,
    )
    base = [Contract.id.in_(select(scoped.c.id))]

    def _agg_stmt(label_expr, *, order_desc: bool = False, order_by_amount: bool = False, limit: int | None = None):
        labeled = label_expr.label("label")
        amount_sum = func.coalesce(func.sum(Contract.amount_total), 0).label("amount")
        stmt = select(
            labeled,
            func.count(Contract.id).label("count"),
            amount_sum,
        ).where(*base).group_by(labeled)
        if order_by_amount:
            stmt = stmt.order_by(amount_sum.desc() if order_desc else amount_sum.asc())
        else:
            stmt = stmt.order_by(labeled.desc() if order_desc else labeled.asc())
        if limit:
            stmt = stmt.limit(limit)
        return stmt

    # 汇总指标
    row = (await db.execute(
        select(
            func.count(Contract.id),
            func.coalesce(func.sum(Contract.amount_total), 0),
        ).where(*base)
    )).one()
    total_count = int(row[0] or 0)
    total_amount = float(row[1] or 0)

    today = date.today()
    today_scoped = await _scoped_contract_ids(
        db, tenant_id, user,
        customer_name=customer_name,
        customer_names=customer_names,
        customer_op=customer_op,
        customer_match=customer_match,
        card_date_op="eq",
        card_from=None,
        card_to=None,
        card_date=today,
        department_id=department_id,
        department_ids=department_ids,
        department_op=department_op,
        assignee_id=assignee_id,
        assignee_ids=assignee_ids,
        assignee_op=assignee_op,
    )
    today_row = (await db.execute(
        select(func.coalesce(func.sum(Contract.amount_total), 0)).where(
            Contract.id.in_(select(today_scoped.c.id)),
        )
    )).scalar()
    today_amount = float(today_row or 0)

    year_label = func.coalesce(func.to_char(Contract.card_date, "YYYY"), literal("未知"))
    month_label = func.coalesce(func.to_char(Contract.card_date, "YYYY-MM"), literal("未知"))
    dept_label = func.coalesce(Contract.department_name, literal("未填写"))
    sales_label = func.coalesce(Contract.assignee_name, literal("未填写"))

    # 按年（年度合同额）
    year_rows = (await db.execute(_agg_stmt(year_label, order_desc=True))).all()

    # 按月
    month_rows = (await db.execute(_agg_stmt(month_label))).all()

    # 按部门
    dept_rows = (await db.execute(_agg_stmt(dept_label, order_desc=True, order_by_amount=True))).all()

    # 业务人员
    sales_rows = (await db.execute(_agg_stmt(sales_label, order_desc=True, order_by_amount=True, limit=11))).all()

    # 前10大客户
    cust_label = func.coalesce(
        Customer.name,
        Contract.registration_json["customer_name"].as_string(),
        literal("未知"),
    ).label("label")
    top_cust_rows = (await db.execute(
        select(
            cust_label,
            func.count(Contract.id).label("count"),
            func.coalesce(func.sum(Contract.amount_total), 0).label("amount"),
        )
        .select_from(Contract)
        .outerjoin(Customer, and_(Customer.id == Contract.customer_id, Customer.tenant_id == tenant_id))
        .where(*base)
        .group_by(cust_label)
        .order_by(func.coalesce(func.sum(Contract.amount_total), 0).desc())
        .limit(10)
    )).all()

    def _pack(rows) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append({
                "label": str(r.label or "未知"),
                "count": int(r.count or 0),
                "amount": float(r.amount or 0),
            })
        return out

    year_amount = total_amount
    if year_rows:
        # 筛选年内通常只有一条；多选年份时取合计
        year_amount = sum(float(r.amount or 0) for r in year_rows)

    by_industry_contract = await _contract_industry_amount(db, tenant_id, base)
    dept_workload = await _dept_workload_stats(db, base)
    dept_month_stats = await _dept_month_stats(db, base)

    customers: dict[str, Any] | None = None
    perms = user.get("permissions") or []
    if "customer:view" in perms:
        customers = await _customer_dashboard_stats(
            db, tenant_id, user,
            customer_name=customer_name,
            card_from=card_from,
            card_to=card_to,
        )

    return {
        "count": total_count,
        "amount_total": total_amount,
        "year_amount": year_amount,
        "today_amount": today_amount,
        "card_date_from": str(card_from) if card_from else None,
        "card_date_to": str(card_to) if card_to else None,
        "by_year": _pack(year_rows),
        "by_month": _pack(month_rows),
        "by_department": _pack(dept_rows),
        "by_sales": _pack(sales_rows),
        "top_customers": _pack(top_cust_rows),
        "by_industry_contract": by_industry_contract,
        "dept_workload": dept_workload,
        "dept_month_stats": dept_month_stats,
        "customers": customers,
    }
