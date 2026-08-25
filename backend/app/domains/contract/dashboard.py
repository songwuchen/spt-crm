"""合同管理仪表盘 — 对齐简道云「合同管理仪表盘」聚合口径。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contract.models import Contract
from app.domains.customer.models import Customer
from app.domains.project.models import OpportunityProject


def _customer_name_clause(tenant_id: str, customer_name: str):
    """按展示用客户名称筛选：直连 customer_id、商机客户、登记 JSON 兜底。"""
    kw = (customer_name or "").strip()
    if not kw:
        return None
    like = f"%{kw}%"
    matching_customers = select(Customer.id).where(
        Customer.tenant_id == tenant_id,
        Customer.name.ilike(like),
    )
    via_direct = Contract.customer_id.in_(matching_customers)
    via_project = Contract.project_id.in_(
        select(OpportunityProject.id).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.customer_id.in_(matching_customers),
        )
    )
    via_reg = Contract.registration_json["customer_name"].as_string().ilike(like)
    return or_(via_direct, via_project, via_reg)


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
    card_from: date | None,
    card_to: date | None,
    department_id: str | None,
    assignee_id: str | None,
):
    from app.common.data_scope import apply_project_child_scope

    conds: list = [Contract.tenant_id == tenant_id]
    if card_from:
        conds.append(Contract.card_date >= card_from)
    if card_to:
        conds.append(Contract.card_date <= card_to)
    if department_id:
        conds.append(Contract.department_id == department_id)
    if assignee_id:
        conds.append(Contract.assignee_id == assignee_id)
    cust = _customer_name_clause(tenant_id, customer_name or "")
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
    card_date_from: str | None = None,
    card_date_to: str | None = None,
    department_id: str | None = None,
    assignee_id: str | None = None,
) -> dict[str, Any]:
    card_from = _parse_date(card_date_from)
    card_to = _parse_date(card_date_to)
    if card_from is None and card_to is None:
        today = date.today()
        card_from = date(today.year, 1, 1)
        card_to = date(today.year, 12, 31)

    scoped = await _scoped_contract_ids(
        db, tenant_id, user,
        customer_name=customer_name,
        card_from=card_from,
        card_to=card_to,
        department_id=department_id,
        assignee_id=assignee_id,
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
        card_from=today,
        card_to=today,
        department_id=department_id,
        assignee_id=assignee_id,
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
        "customers": customers,
    }
