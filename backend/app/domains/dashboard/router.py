import io
from datetime import datetime, timezone, date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, extract, or_
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel, Field
from typing import Optional
from app.dependencies import get_db, get_tenant_id, get_current_user, require_permissions
from app.common.schemas import ok
from app.domains.customer.models import Customer
from app.domains.lead.models import Lead
from app.domains.project.models import OpportunityProject
from app.domains.quote.models import Quote
from app.domains.solution.models import Solution
from app.domains.delivery.models import DeliveryMilestone
from app.domains.payment.models import Invoice, PaymentRecord
from app.domains.change.models import ChangeRequest
from app.domains.service_ticket.models import ServiceTicket
from app.domains.activity.models import Activity
from app.domains.ai_center.models import AiTask
from app.domains.contract.models import Contract
from app.domains.payment.models import PaymentPlan
from app.domains.dashboard.models import SalesTarget, DashboardSnapshot

router = APIRouter(prefix="/api/v1/dashboard", tags=["工作台"])


@router.get("/stats")
async def stats(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    customer_total = (await db.execute(
        select(func.count(Customer.id)).where(Customer.tenant_id == tenant_id)
    )).scalar() or 0

    lead_total = (await db.execute(
        select(func.count(Lead.id)).where(Lead.tenant_id == tenant_id)
    )).scalar() or 0

    monthly_new_customers = (await db.execute(
        select(func.count(Customer.id)).where(
            Customer.tenant_id == tenant_id,
            extract("year", Customer.created_at) == now.year,
            extract("month", Customer.created_at) == now.month,
        )
    )).scalar() or 0

    pending_leads = (await db.execute(
        select(func.count(Lead.id)).where(
            Lead.tenant_id == tenant_id,
            Lead.status.in_(["new", "following"]),
        )
    )).scalar() or 0

    project_total = (await db.execute(
        select(func.count(OpportunityProject.id)).where(OpportunityProject.tenant_id == tenant_id)
    )).scalar() or 0

    active_projects = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.status == "active",
        )
    )).scalar() or 0

    quote_total = (await db.execute(
        select(func.count(Quote.id)).where(Quote.tenant_id == tenant_id)
    )).scalar() or 0

    solution_total = (await db.execute(
        select(func.count(Solution.id)).where(Solution.tenant_id == tenant_id)
    )).scalar() or 0

    milestone_total = (await db.execute(
        select(func.count(DeliveryMilestone.id)).where(DeliveryMilestone.tenant_id == tenant_id)
    )).scalar() or 0

    milestone_delayed = (await db.execute(
        select(func.count(DeliveryMilestone.id)).where(
            DeliveryMilestone.tenant_id == tenant_id,
            DeliveryMilestone.status == "delayed",
        )
    )).scalar() or 0

    invoice_total = (await db.execute(
        select(func.count(Invoice.id)).where(Invoice.tenant_id == tenant_id)
    )).scalar() or 0

    payment_received = (await db.execute(
        select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
            PaymentRecord.tenant_id == tenant_id,
        )
    )).scalar() or 0

    change_total = (await db.execute(
        select(func.count(ChangeRequest.id)).where(ChangeRequest.tenant_id == tenant_id)
    )).scalar() or 0

    ticket_total = (await db.execute(
        select(func.count(ServiceTicket.id)).where(ServiceTicket.tenant_id == tenant_id)
    )).scalar() or 0

    ticket_open = (await db.execute(
        select(func.count(ServiceTicket.id)).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.status.in_(["open", "assigned", "in_progress"]),
        )
    )).scalar() or 0

    activity_total = (await db.execute(
        select(func.count(Activity.id)).where(Activity.tenant_id == tenant_id)
    )).scalar() or 0

    ai_task_total = (await db.execute(
        select(func.count(AiTask.id)).where(AiTask.tenant_id == tenant_id)
    )).scalar() or 0

    # Pipeline value
    pipeline_value = (await db.execute(
        select(func.coalesce(func.sum(OpportunityProject.amount_expect), 0)).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.status == "active",
        )
    )).scalar() or 0

    contract_total = (await db.execute(
        select(func.count(Contract.id)).where(Contract.tenant_id == tenant_id)
    )).scalar() or 0

    return ok({
        "customer_total": customer_total,
        "lead_total": lead_total,
        "monthly_new_customers": monthly_new_customers,
        "pending_leads": pending_leads,
        "project_total": project_total,
        "active_projects": active_projects,
        "quote_total": quote_total,
        "solution_total": solution_total,
        "milestone_total": milestone_total,
        "milestone_delayed": milestone_delayed,
        "invoice_total": invoice_total,
        "payment_received": payment_received,
        "change_total": change_total,
        "ticket_total": ticket_total,
        "ticket_open": ticket_open,
        "activity_total": activity_total,
        "ai_task_total": ai_task_total,
        "pipeline_value": float(pipeline_value),
        "contract_total": contract_total,
    })


@router.get("/trends")
async def trends(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Month-over-month trends for key metrics."""
    now = datetime.now(timezone.utc)
    # Current month
    cur_year, cur_month = now.year, now.month
    # Previous month
    prev_month = cur_month - 1
    prev_year = cur_year
    if prev_month <= 0:
        prev_month += 12
        prev_year -= 1

    def _month_filter(model_cls, date_col, y, m):
        col = getattr(model_cls, date_col)
        return select(func.count(model_cls.id)).where(
            model_cls.tenant_id == tenant_id,
            extract("year", col) == y,
            extract("month", col) == m,
        )

    cur_customers = (await db.execute(_month_filter(Customer, "created_at", cur_year, cur_month))).scalar() or 0
    prev_customers = (await db.execute(_month_filter(Customer, "created_at", prev_year, prev_month))).scalar() or 0

    cur_leads = (await db.execute(_month_filter(Lead, "created_at", cur_year, cur_month))).scalar() or 0
    prev_leads = (await db.execute(_month_filter(Lead, "created_at", prev_year, prev_month))).scalar() or 0

    cur_projects = (await db.execute(_month_filter(OpportunityProject, "created_at", cur_year, cur_month))).scalar() or 0
    prev_projects = (await db.execute(_month_filter(OpportunityProject, "created_at", prev_year, prev_month))).scalar() or 0

    cur_tickets = (await db.execute(_month_filter(ServiceTicket, "created_at", cur_year, cur_month))).scalar() or 0
    prev_tickets = (await db.execute(_month_filter(ServiceTicket, "created_at", prev_year, prev_month))).scalar() or 0

    def _trend(cur: int, prev: int) -> dict:
        diff = cur - prev
        if prev == 0:
            pct = 100 if cur > 0 else 0
        else:
            pct = round((diff / prev) * 100)
        return {"current": cur, "previous": prev, "diff": diff, "pct": pct}

    return ok({
        "customers": _trend(cur_customers, prev_customers),
        "leads": _trend(cur_leads, prev_leads),
        "projects": _trend(cur_projects, prev_projects),
        "tickets": _trend(cur_tickets, prev_tickets),
    })


@router.get("/alerts")
async def alerts(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Dashboard alerts: stalled projects, overdue milestones, high-risk projects."""
    now = datetime.now(timezone.utc)
    alerts_list = []

    # Stalled projects (no update in 14+ days)
    from sqlalchemy import text
    stalled = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.status == "active",
            OpportunityProject.updated_at < func.now() - text("interval '14 days'"),
        ).order_by(OpportunityProject.updated_at.asc()).limit(10)
    )).scalars().all()
    for p in stalled:
        days = (now - p.updated_at.replace(tzinfo=timezone.utc)).days if p.updated_at else 0
        alerts_list.append({
            "type": "stalled", "severity": "warning" if days < 30 else "critical",
            "title": f"商机停滞 {days} 天",
            "content": p.name,
            "biz_type": "project", "biz_id": p.id,
        })

    # Delayed milestones
    delayed = (await db.execute(
        select(DeliveryMilestone).where(
            DeliveryMilestone.tenant_id == tenant_id,
            DeliveryMilestone.status == "delayed",
        ).limit(10)
    )).scalars().all()
    for m in delayed:
        alerts_list.append({
            "type": "milestone_delayed", "severity": "warning",
            "title": f"里程碑延期: {m.name or m.milestone_code}",
            "content": f"计划日期: {m.plan_date}",
            "biz_type": "project", "biz_id": m.project_id,
        })

    # High risk projects
    high_risk = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.status == "active",
            OpportunityProject.risk_level == "H",
        ).limit(10)
    )).scalars().all()
    for p in high_risk:
        alerts_list.append({
            "type": "high_risk", "severity": "critical",
            "title": "高风险商机",
            "content": p.name,
            "biz_type": "project", "biz_id": p.id,
        })

    # Open tickets
    open_tickets = (await db.execute(
        select(ServiceTicket).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.status.in_(["open"]),
            ServiceTicket.priority.in_(["high", "critical"]),
        ).limit(10)
    )).scalars().all()
    for t in open_tickets:
        alerts_list.append({
            "type": "urgent_ticket", "severity": "warning",
            "title": f"紧急工单: {t.ticket_no}",
            "content": t.description[:50] if t.description else "",
            "biz_type": "service_ticket", "biz_id": t.id,
        })

    # Overdue payments
    from datetime import timedelta
    overdue_plans = (await db.execute(
        select(PaymentPlan).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.status == "pending",
            PaymentPlan.due_date != None,
            PaymentPlan.due_date < date.today(),
        ).limit(10)
    )).scalars().all()
    for p in overdue_plans:
        overdue_days = (date.today() - p.due_date).days
        alerts_list.append({
            "type": "payment_overdue", "severity": "critical" if overdue_days > 30 else "warning",
            "title": f"回款逾期 {overdue_days} 天: {p.plan_no}",
            "content": f"金额: ¥{float(p.amount or 0):,.0f}，到期: {p.due_date}",
            "biz_type": "project", "biz_id": p.project_id,
        })

    # Large amount projects with no quote
    big_no_quote = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.status == "active",
            OpportunityProject.amount_expect > 100000,
            OpportunityProject.stage_code.in_(["S3", "S4"]),
        ).limit(10)
    )).scalars().all()
    for p in big_no_quote:
        has_quote = (await db.execute(
            select(func.count()).where(Quote.project_id == p.id, Quote.tenant_id == tenant_id)
        )).scalar()
        if not has_quote:
            alerts_list.append({
                "type": "no_quote", "severity": "info",
                "title": f"大额商机未报价: {p.name}",
                "content": f"预期金额 ¥{float(p.amount_expect or 0):,.0f}，阶段 {p.stage_code}",
                "biz_type": "project", "biz_id": p.id,
            })

    return ok(alerts_list)


@router.get("/funnel")
async def funnel(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Sales funnel: count + amount by stage for active projects."""
    stages = ["S1", "S2", "S3", "S4", "S5", "S6"]
    stage_labels = {"S1": "线索确认", "S2": "需求分析", "S3": "方案报价", "S4": "商务谈判", "S5": "合同签订", "S6": "交付验收"}
    result = []
    for s in stages:
        row = await db.execute(
            select(
                func.count(OpportunityProject.id),
                func.coalesce(func.sum(OpportunityProject.amount_expect), 0),
            ).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.status == "active",
                OpportunityProject.stage_code == s,
            )
        )
        count, amount = row.one()
        result.append({
            "stage": s, "label": stage_labels[s],
            "count": count, "amount": float(amount),
        })
    return ok(result)


@router.get("/win_loss")
async def win_loss(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Win/loss stats."""
    won_count = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.status == "won"
        )
    )).scalar() or 0
    lost_count = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.status == "lost"
        )
    )).scalar() or 0
    won_amount = (await db.execute(
        select(func.coalesce(func.sum(OpportunityProject.amount_expect), 0)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.status == "won"
        )
    )).scalar() or 0
    lost_amount = (await db.execute(
        select(func.coalesce(func.sum(OpportunityProject.amount_expect), 0)).where(
            OpportunityProject.tenant_id == tenant_id, OpportunityProject.status == "lost"
        )
    )).scalar() or 0
    total = won_count + lost_count
    win_rate = round(won_count / total * 100, 1) if total > 0 else 0

    return ok({
        "won_count": won_count, "lost_count": lost_count,
        "won_amount": float(won_amount), "lost_amount": float(lost_amount),
        "win_rate": win_rate,
    })


@router.get("/top_customers")
async def top_customers(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Top 10 customers by project pipeline value."""
    from app.domains.customer.models import Customer
    result = await db.execute(
        select(
            Customer.id, Customer.name,
            func.count(OpportunityProject.id).label("project_count"),
            func.coalesce(func.sum(OpportunityProject.amount_expect), 0).label("total_amount"),
        ).join(
            OpportunityProject, OpportunityProject.customer_id == Customer.id
        ).where(
            Customer.tenant_id == tenant_id,
            OpportunityProject.status == "active",
        ).group_by(Customer.id, Customer.name)
        .order_by(func.sum(OpportunityProject.amount_expect).desc())
        .limit(10)
    )
    rows = result.all()
    return ok([{
        "id": r.id, "name": r.name,
        "project_count": r.project_count,
        "total_amount": float(r.total_amount),
    } for r in rows])


@router.get("/payment_overview")
async def payment_overview(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Payment overview: total planned, received, overdue."""
    from app.domains.payment.service import mark_overdue_plans
    await mark_overdue_plans(db, tenant_id)

    from sqlalchemy import text, cast, Date as SaDate
    now = datetime.now(timezone.utc).date()

    # Total planned
    total_planned = (await db.execute(
        select(func.coalesce(func.sum(PaymentPlan.amount), 0)).where(
            PaymentPlan.tenant_id == tenant_id,
        )
    )).scalar() or 0

    # Total received
    total_received = (await db.execute(
        select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
            PaymentRecord.tenant_id == tenant_id,
        )
    )).scalar() or 0

    # Overdue plans
    overdue_count = (await db.execute(
        select(func.count(PaymentPlan.id)).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.status.in_(["pending", "overdue"]),
            PaymentPlan.due_date < now,
        )
    )).scalar() or 0

    overdue_amount = (await db.execute(
        select(func.coalesce(func.sum(PaymentPlan.amount), 0)).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.status.in_(["pending", "overdue"]),
            PaymentPlan.due_date < now,
        )
    )).scalar() or 0

    # Upcoming 30 days
    from datetime import timedelta
    upcoming_date = now + timedelta(days=30)
    upcoming_amount = (await db.execute(
        select(func.coalesce(func.sum(PaymentPlan.amount), 0)).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.status == "pending",
            PaymentPlan.due_date >= now,
            PaymentPlan.due_date <= upcoming_date,
        )
    )).scalar() or 0

    return ok({
        "total_planned": float(total_planned),
        "total_received": float(total_received),
        "overdue_count": overdue_count,
        "overdue_amount": float(overdue_amount),
        "upcoming_30d_amount": float(upcoming_amount),
        "collection_rate": round(float(total_received) / float(total_planned) * 100, 1) if total_planned else 0,
    })


@router.get("/milestone_overview")
async def milestone_overview(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delivery milestone overview by status."""
    # Model uses: not_start/doing/done/delayed
    # Map to readable keys for frontend
    status_map = {
        "not_start": "pending",
        "doing": "in_progress",
        "done": "completed",
        "delayed": "delayed",
    }
    result = {}
    for db_status, display_key in status_map.items():
        count = (await db.execute(
            select(func.count(DeliveryMilestone.id)).where(
                DeliveryMilestone.tenant_id == tenant_id,
                DeliveryMilestone.status == db_status,
            )
        )).scalar() or 0
        result[display_key] = count
    total = sum(result.values())
    result["total"] = total
    result["completion_rate"] = round(result.get("completed", 0) / total * 100, 1) if total else 0
    return ok(result)


@router.get("/monthly_revenue")
async def monthly_revenue(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Monthly revenue (payment received) for the last 6 months."""
    now = datetime.now(timezone.utc)
    months = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        amount = (await db.execute(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id,
                extract("year", PaymentRecord.received_date) == y,
                extract("month", PaymentRecord.received_date) == m,
            )
        )).scalar() or 0
        months.append({
            "year": y, "month": m,
            "label": f"{y}-{str(m).zfill(2)}",
            "amount": float(amount),
        })
    return ok(months)


@router.get("/leaderboard")
async def leaderboard(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Performance leaderboard: top salespeople by won deals."""
    # Won deals by owner
    result = await db.execute(
        select(
            OpportunityProject.owner_id,
            OpportunityProject.owner_name,
            func.count(OpportunityProject.id).label("won_count"),
            func.coalesce(func.sum(OpportunityProject.amount_expect), 0).label("won_amount"),
        ).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.status == "won",
            OpportunityProject.owner_id.isnot(None),
        ).group_by(OpportunityProject.owner_id, OpportunityProject.owner_name)
        .order_by(func.sum(OpportunityProject.amount_expect).desc())
        .limit(10)
    )
    won_rows = result.all()

    # Active pipeline by owner
    pipeline_result = await db.execute(
        select(
            OpportunityProject.owner_id,
            func.count(OpportunityProject.id).label("active_count"),
            func.coalesce(func.sum(OpportunityProject.amount_expect), 0).label("pipeline_amount"),
        ).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.status == "active",
            OpportunityProject.owner_id.isnot(None),
        ).group_by(OpportunityProject.owner_id)
    )
    pipeline_map = {r.owner_id: {"active_count": r.active_count, "pipeline_amount": float(r.pipeline_amount)} for r in pipeline_result.all()}

    board = []
    for r in won_rows:
        p = pipeline_map.get(r.owner_id, {"active_count": 0, "pipeline_amount": 0})
        board.append({
            "owner_id": r.owner_id,
            "owner_name": r.owner_name or "未知",
            "won_count": r.won_count,
            "won_amount": float(r.won_amount),
            "active_count": p["active_count"],
            "pipeline_amount": p["pipeline_amount"],
        })

    return ok(board)


@router.get("/trend")
async def trend(
    period: str = Query("month"),
    months: int = Query(6, ge=1, le=24),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Monthly trend: new opportunities, won, lost, and pipeline amount."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    result = []
    for i in range(months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1

        new_count = (await db.execute(
            select(func.count(OpportunityProject.id)).where(
                OpportunityProject.tenant_id == tenant_id,
                extract("year", OpportunityProject.created_at) == y,
                extract("month", OpportunityProject.created_at) == m,
            )
        )).scalar() or 0

        won_count = (await db.execute(
            select(func.count(OpportunityProject.id)).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.status == "won",
                extract("year", OpportunityProject.updated_at) == y,
                extract("month", OpportunityProject.updated_at) == m,
            )
        )).scalar() or 0

        lost_count = (await db.execute(
            select(func.count(OpportunityProject.id)).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.status == "lost",
                extract("year", OpportunityProject.updated_at) == y,
                extract("month", OpportunityProject.updated_at) == m,
            )
        )).scalar() or 0

        won_amount = (await db.execute(
            select(func.coalesce(func.sum(OpportunityProject.amount_expect), 0)).where(
                OpportunityProject.tenant_id == tenant_id,
                OpportunityProject.status == "won",
                extract("year", OpportunityProject.updated_at) == y,
                extract("month", OpportunityProject.updated_at) == m,
            )
        )).scalar() or 0

        result.append({
            "label": f"{y}-{str(m).zfill(2)}",
            "year": y, "month": m,
            "new": new_count, "won": won_count, "lost": lost_count,
            "won_amount": float(won_amount),
        })
    return ok(result)


@router.get("/collection")
async def collection(
    months: int = Query(6, ge=1, le=24),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Monthly collection analysis: receivable, received, overdue."""
    now = datetime.now(timezone.utc)
    result = []
    for i in range(months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1

        # Planned (due in this month)
        receivable = (await db.execute(
            select(func.coalesce(func.sum(PaymentPlan.amount), 0)).where(
                PaymentPlan.tenant_id == tenant_id,
                extract("year", PaymentPlan.due_date) == y,
                extract("month", PaymentPlan.due_date) == m,
            )
        )).scalar() or 0

        # Received in this month
        received = (await db.execute(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id,
                extract("year", PaymentRecord.received_date) == y,
                extract("month", PaymentRecord.received_date) == m,
            )
        )).scalar() or 0

        # Overdue plans in this month (due in this month, status overdue or pending past due)
        import calendar
        last_day = calendar.monthrange(y, m)[1]
        from datetime import date as date_type
        month_end = date_type(y, m, last_day)
        today = now.date()
        overdue = 0
        if month_end <= today:
            overdue = (await db.execute(
                select(func.coalesce(func.sum(PaymentPlan.amount), 0)).where(
                    PaymentPlan.tenant_id == tenant_id,
                    PaymentPlan.status.in_(["pending", "overdue"]),
                    extract("year", PaymentPlan.due_date) == y,
                    extract("month", PaymentPlan.due_date) == m,
                )
            )).scalar() or 0

        result.append({
            "label": f"{y}-{str(m).zfill(2)}",
            "receivable": float(receivable),
            "received": float(received),
            "overdue": float(overdue),
        })
    return ok(result)


@router.get("/my_overview")
async def my_overview(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Personal dashboard: my customers, projects, expiring contracts, pending items."""
    from datetime import timedelta
    uid = user["sub"]
    now = datetime.now(timezone.utc)

    # My customers
    my_customer_count = (await db.execute(
        select(func.count(Customer.id)).where(
            Customer.tenant_id == tenant_id, Customer.owner_id == uid,
        )
    )).scalar() or 0

    # My active projects
    my_active_projects = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.owner_id == uid,
            OpportunityProject.status == "active",
        )
    )).scalar() or 0

    # My pipeline value
    my_pipeline = (await db.execute(
        select(func.coalesce(func.sum(OpportunityProject.amount_expect), 0)).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.owner_id == uid,
            OpportunityProject.status == "active",
        )
    )).scalar() or 0

    # My won deals this month
    my_won_month = (await db.execute(
        select(func.count(OpportunityProject.id)).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.owner_id == uid,
            OpportunityProject.status == "won",
            extract("year", OpportunityProject.updated_at) == now.year,
            extract("month", OpportunityProject.updated_at) == now.month,
        )
    )).scalar() or 0

    # My pending leads
    my_pending_leads = (await db.execute(
        select(func.count(Lead.id)).where(
            Lead.tenant_id == tenant_id,
            Lead.owner_id == uid,
            Lead.status.in_(["new", "following"]),
        )
    )).scalar() or 0

    # My open tickets
    my_open_tickets = (await db.execute(
        select(func.count(ServiceTicket.id)).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.assigned_to_id == uid,
            ServiceTicket.status.in_(["open", "assigned", "in_progress"]),
        )
    )).scalar() or 0

    # Expiring contracts (next 30 days) — contracts linked to my projects
    from sqlalchemy import text as sa_text
    expiring_rows = (await db.execute(
        select(
            Contract.id, Contract.contract_no, Contract.amount_total,
            Contract.signed_date, OpportunityProject.name.label("project_name"),
        ).join(
            OpportunityProject, OpportunityProject.id == Contract.project_id
        ).where(
            Contract.tenant_id == tenant_id,
            OpportunityProject.owner_id == uid,
            Contract.status == "signed",
        ).order_by(Contract.signed_date.desc()).limit(5)
    )).all()
    expiring_contracts = [{
        "id": r.id, "contract_no": r.contract_no,
        "amount_total": float(r.amount_total) if r.amount_total else 0,
        "project_name": r.project_name,
        "signed_date": str(r.signed_date) if r.signed_date else None,
    } for r in expiring_rows]

    # My stalled projects (no update in 7+ days)
    stalled_rows = (await db.execute(
        select(
            OpportunityProject.id, OpportunityProject.name,
            OpportunityProject.stage_code, OpportunityProject.updated_at,
        ).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.owner_id == uid,
            OpportunityProject.status == "active",
            OpportunityProject.updated_at < func.now() - sa_text("interval '7 days'"),
        ).order_by(OpportunityProject.updated_at.asc()).limit(5)
    )).all()
    stalled_projects = [{
        "id": r.id, "name": r.name, "stage_code": r.stage_code,
        "days_stalled": (now - r.updated_at.replace(tzinfo=timezone.utc)).days if r.updated_at else 0,
    } for r in stalled_rows]

    return ok({
        "my_customer_count": my_customer_count,
        "my_active_projects": my_active_projects,
        "my_pipeline": float(my_pipeline),
        "my_won_month": my_won_month,
        "my_pending_leads": my_pending_leads,
        "my_open_tickets": my_open_tickets,
        "expiring_contracts": expiring_contracts,
        "stalled_projects": stalled_projects,
    })


@router.get("/search")
async def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Global search across customers, leads, projects, contacts, tickets."""
    keyword = f"%{q}%"
    results = []
    LIMIT = 5

    # Customers
    rows = (await db.execute(
        select(Customer.id, Customer.name, Customer.customer_code).where(
            Customer.tenant_id == tenant_id,
            or_(Customer.name.ilike(keyword), Customer.customer_code.ilike(keyword), Customer.short_name.ilike(keyword)),
        ).limit(LIMIT)
    )).all()
    for r in rows:
        results.append({"type": "customer", "id": r.id, "title": r.name, "subtitle": r.customer_code or "", "url": f"/customers/{r.id}"})

    # Leads
    rows = (await db.execute(
        select(Lead.id, Lead.lead_code, Lead.title, Lead.company_name, Lead.contact_name).where(
            Lead.tenant_id == tenant_id,
            or_(Lead.title.ilike(keyword), Lead.company_name.ilike(keyword), Lead.contact_name.ilike(keyword), Lead.lead_code.ilike(keyword)),
        ).limit(LIMIT)
    )).all()
    for r in rows:
        results.append({"type": "lead", "id": r.id, "title": r.title or r.company_name or r.contact_name, "subtitle": r.lead_code or "", "url": f"/leads/{r.id}"})

    # Projects
    rows = (await db.execute(
        select(OpportunityProject.id, OpportunityProject.name, OpportunityProject.project_code).where(
            OpportunityProject.tenant_id == tenant_id,
            or_(OpportunityProject.name.ilike(keyword), OpportunityProject.project_code.ilike(keyword)),
        ).limit(LIMIT)
    )).all()
    for r in rows:
        results.append({"type": "project", "id": r.id, "title": r.name, "subtitle": r.project_code or "", "url": f"/opportunities/{r.id}"})

    # Contacts
    from app.domains.customer.models import Contact
    rows = (await db.execute(
        select(Contact.id, Contact.name, Contact.phone, Contact.customer_id).where(
            Contact.tenant_id == tenant_id,
            or_(Contact.name.ilike(keyword), Contact.phone.ilike(keyword), Contact.email.ilike(keyword)),
        ).limit(LIMIT)
    )).all()
    for r in rows:
        results.append({"type": "contact", "id": r.id, "title": r.name, "subtitle": r.phone or "", "url": f"/customers/{r.customer_id}"})

    # Service Tickets
    rows = (await db.execute(
        select(ServiceTicket.id, ServiceTicket.ticket_no, ServiceTicket.description).where(
            ServiceTicket.tenant_id == tenant_id,
            or_(ServiceTicket.ticket_no.ilike(keyword), ServiceTicket.description.ilike(keyword)),
        ).limit(LIMIT)
    )).all()
    for r in rows:
        results.append({"type": "ticket", "id": r.id, "title": r.ticket_no, "subtitle": (r.description or "")[:50], "url": f"/service-tickets/{r.id}"})

    return ok(results)


# ---- Sales Targets ----

class SalesTargetBody(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    target_amount: float = Field(..., ge=0)
    target_count: Optional[int] = Field(None, ge=0)


@router.get("/targets")
async def list_targets(
    year: int = Query(...),
    month: int = Query(None),
    user_id: str = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    q = select(SalesTarget).where(SalesTarget.tenant_id == tenant_id, SalesTarget.year == year)
    if month:
        q = q.where(SalesTarget.month == month)
    if user_id:
        q = q.where(SalesTarget.user_id == user_id)
    items = (await db.execute(q.order_by(SalesTarget.month, SalesTarget.user_name))).scalars().all()
    return ok([{
        "id": t.id, "user_id": t.user_id, "user_name": t.user_name,
        "year": t.year, "month": t.month,
        "target_amount": float(t.target_amount), "target_count": t.target_count,
    } for t in items])


@router.post("/targets")
async def upsert_target(
    body: SalesTargetBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    """Create or update a sales target (upsert by user+year+month)."""
    existing = (await db.execute(
        select(SalesTarget).where(
            SalesTarget.tenant_id == tenant_id,
            SalesTarget.user_id == body.user_id,
            SalesTarget.year == body.year,
            SalesTarget.month == body.month,
        )
    )).scalar()
    if existing:
        existing.target_amount = body.target_amount
        existing.target_count = body.target_count
        existing.user_name = body.user_name or existing.user_name
        await db.commit()
        await db.refresh(existing)
        t = existing
    else:
        t = SalesTarget(
            tenant_id=tenant_id,
            user_id=body.user_id, user_name=body.user_name,
            year=body.year, month=body.month,
            target_amount=body.target_amount, target_count=body.target_count,
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
    return ok({"id": t.id, "user_id": t.user_id, "year": t.year, "month": t.month, "target_amount": float(t.target_amount)})


@router.delete("/targets/{target_id}")
async def delete_target(
    target_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("role:manage")),
):
    t = (await db.execute(
        select(SalesTarget).where(SalesTarget.tenant_id == tenant_id, SalesTarget.id == target_id)
    )).scalar()
    if not t:
        from app.common.exceptions import BusinessException
        raise BusinessException("目标不存在")
    await db.delete(t)
    await db.commit()
    return ok()


@router.get("/target_achievement")
async def target_achievement(
    year: int = Query(...),
    month: int = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get target vs actual achievement for all users."""
    # Get targets
    tq = select(SalesTarget).where(SalesTarget.tenant_id == tenant_id, SalesTarget.year == year)
    if month:
        tq = tq.where(SalesTarget.month == month)
    targets = (await db.execute(tq)).scalars().all()

    # Get actual won amounts by owner
    aq = select(
        OpportunityProject.owner_id,
        OpportunityProject.owner_name,
        func.coalesce(func.sum(OpportunityProject.amount_expect), 0).label("actual_amount"),
        func.count(OpportunityProject.id).label("actual_count"),
    ).where(
        OpportunityProject.tenant_id == tenant_id,
        OpportunityProject.status == "won",
        extract("year", OpportunityProject.updated_at) == year,
    )
    if month:
        aq = aq.where(extract("month", OpportunityProject.updated_at) == month)
    aq = aq.group_by(OpportunityProject.owner_id, OpportunityProject.owner_name)
    actuals = {r.owner_id: {"actual_amount": float(r.actual_amount), "actual_count": r.actual_count, "owner_name": r.owner_name}
               for r in (await db.execute(aq)).all()}

    # Merge
    user_targets: dict = {}
    for t in targets:
        key = t.user_id
        if key not in user_targets:
            user_targets[key] = {"user_id": t.user_id, "user_name": t.user_name, "target_amount": 0, "target_count": 0}
        user_targets[key]["target_amount"] += float(t.target_amount)
        user_targets[key]["target_count"] += (t.target_count or 0)

    result = []
    all_users = set(list(user_targets.keys()) + list(actuals.keys()))
    for uid in all_users:
        t = user_targets.get(uid, {"user_id": uid, "user_name": actuals.get(uid, {}).get("owner_name", ""), "target_amount": 0, "target_count": 0})
        a = actuals.get(uid, {"actual_amount": 0, "actual_count": 0})
        target_amt = t["target_amount"]
        actual_amt = a["actual_amount"]
        rate = round(actual_amt / target_amt * 100, 1) if target_amt > 0 else 0
        result.append({
            "user_id": uid,
            "user_name": t["user_name"],
            "target_amount": target_amt,
            "target_count": t["target_count"],
            "actual_amount": actual_amt,
            "actual_count": a["actual_count"],
            "achievement_rate": rate,
        })
    result.sort(key=lambda x: x["achievement_rate"], reverse=True)
    return ok(result)


@router.get("/customer_region_stats")
async def customer_region_stats(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Customer distribution by region."""
    rows = (await db.execute(
        select(
            Customer.region,
            func.count(Customer.id).label("count"),
        ).where(
            Customer.tenant_id == tenant_id,
            Customer.is_deleted == False,
            Customer.region.isnot(None),
            Customer.region != "",
        ).group_by(Customer.region)
        .order_by(func.count(Customer.id).desc())
    )).all()

    return ok([{"region": r.region, "count": r.count} for r in rows])


@router.get("/calendar_events")
async def calendar_events(
    year: int = Query(...),
    month: int = Query(...),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Aggregate events for a given month: follow-ups, payment dues, contract expiry, milestones."""
    from datetime import date as date_type, timedelta
    import calendar as cal_mod
    uid = user["sub"]
    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, cal_mod.monthrange(year, month)[1])

    events = []

    # Follow-up activities with next_follow_date
    follow_rows = (await db.execute(
        select(Activity.id, Activity.subject, Activity.next_follow_date).where(
            Activity.tenant_id == tenant_id,
            Activity.created_by_id == uid,
            Activity.next_follow_date.isnot(None),
            Activity.next_follow_date >= first_day,
            Activity.next_follow_date <= last_day,
        )
    )).all()
    for r in follow_rows:
        events.append({
            "id": r.id, "date": str(r.next_follow_date),
            "type": "follow_up", "title": r.subject or "跟进计划",
            "color": "#3b82f6",
        })

    # Payment plans due
    pay_rows = (await db.execute(
        select(PaymentPlan.id, PaymentPlan.due_date, PaymentPlan.amount, PaymentPlan.status).where(
            PaymentPlan.tenant_id == tenant_id,
            PaymentPlan.due_date >= first_day,
            PaymentPlan.due_date <= last_day,
        )
    )).all()
    for r in pay_rows:
        events.append({
            "id": r.id, "date": str(r.due_date),
            "type": "payment_due",
            "title": f"回款¥{float(r.amount)/10000:.1f}万",
            "color": "#f59e0b" if r.status == "pending" else "#ef4444" if r.status == "overdue" else "#10b981",
        })

    # Contract expiry
    contract_rows = (await db.execute(
        select(Contract.id, Contract.contract_no, Contract.end_date).where(
            Contract.tenant_id == tenant_id,
            Contract.status == "signed",
            Contract.end_date.isnot(None),
            Contract.end_date >= first_day,
            Contract.end_date <= last_day,
        )
    )).all()
    for r in contract_rows:
        events.append({
            "id": r.id, "date": str(r.end_date),
            "type": "contract_expiry",
            "title": f"合同到期 {r.contract_no}",
            "color": "#ef4444",
        })

    # Delivery milestones
    milestone_rows = (await db.execute(
        select(DeliveryMilestone.id, DeliveryMilestone.name, DeliveryMilestone.plan_date).where(
            DeliveryMilestone.tenant_id == tenant_id,
            DeliveryMilestone.plan_date.isnot(None),
            DeliveryMilestone.plan_date >= first_day,
            DeliveryMilestone.plan_date <= last_day,
        )
    )).all()
    for r in milestone_rows:
        events.append({
            "id": r.id, "date": str(r.plan_date),
            "type": "milestone",
            "title": r.name or "里程碑",
            "color": "#8b5cf6",
        })

    return ok(events)


@router.get("/contract_expiry")
async def contract_expiry(
    days: int = Query(90, ge=1, le=365),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Contracts expiring within N days."""
    from datetime import timedelta
    now = datetime.now(timezone.utc).date()
    cutoff = now + timedelta(days=days)

    rows = (await db.execute(
        select(
            Contract.id, Contract.contract_no, Contract.project_id, Contract.status,
            Contract.signed_date, Contract.end_date, Contract.amount_total,
            OpportunityProject.name.label("project_name"),
            OpportunityProject.owner_name,
        ).join(
            OpportunityProject, OpportunityProject.id == Contract.project_id
        ).where(
            Contract.tenant_id == tenant_id,
            Contract.status == "signed",
            Contract.end_date.isnot(None),
            Contract.end_date <= cutoff,
        ).order_by(Contract.end_date.asc())
        .limit(50)
    )).all()

    items = []
    for r in rows:
        days_left = (r.end_date - now).days if r.end_date else 0
        items.append({
            "id": r.id,
            "contract_no": r.contract_no,
            "project_id": r.project_id,
            "project_name": r.project_name,
            "owner_name": r.owner_name,
            "amount_total": float(r.amount_total) if r.amount_total else 0,
            "signed_date": str(r.signed_date) if r.signed_date else None,
            "end_date": str(r.end_date) if r.end_date else None,
            "days_left": days_left,
            "urgency": "expired" if days_left < 0 else "critical" if days_left <= 7 else "warning" if days_left <= 30 else "normal",
        })
    return ok(items)


# ---------- Export helpers ----------

async def _gather_export_data(db: AsyncSession, tenant_id: str, start_date: Optional[str], end_date: Optional[str]):
    """Gather analytics summary data for export."""
    filters = [OpportunityProject.tenant_id == tenant_id]
    if start_date:
        filters.append(OpportunityProject.created_at >= start_date)
    if end_date:
        filters.append(OpportunityProject.created_at <= end_date + " 23:59:59")

    # Funnel
    stage_map = {"S1": "线索确认", "S2": "需求分析", "S3": "方案报价", "S4": "商务谈判", "S5": "合同签订", "S6": "交付验收"}
    funnel_rows = (await db.execute(
        select(OpportunityProject.stage, func.count(OpportunityProject.id).label("cnt"),
               func.coalesce(func.sum(OpportunityProject.amount_expect), 0).label("amt"))
        .where(*filters).group_by(OpportunityProject.stage)
    )).all()
    funnel = [{"stage": r.stage, "label": stage_map.get(r.stage, r.stage), "count": r.cnt, "amount": float(r.amt)} for r in funnel_rows]

    # Win/Loss
    won_count = (await db.execute(select(func.count(OpportunityProject.id)).where(*filters, OpportunityProject.status == "won"))).scalar() or 0
    lost_count = (await db.execute(select(func.count(OpportunityProject.id)).where(*filters, OpportunityProject.status == "lost"))).scalar() or 0
    won_amount = float((await db.execute(select(func.coalesce(func.sum(OpportunityProject.amount_expect), 0)).where(*filters, OpportunityProject.status == "won"))).scalar() or 0)
    lost_amount = float((await db.execute(select(func.coalesce(func.sum(OpportunityProject.amount_expect), 0)).where(*filters, OpportunityProject.status == "lost"))).scalar() or 0)
    total_decided = won_count + lost_count
    win_rate = round(won_count / total_decided * 100, 1) if total_decided else 0

    # Top customers
    top_rows = (await db.execute(
        select(Customer.name, func.count(OpportunityProject.id).label("cnt"),
               func.coalesce(func.sum(OpportunityProject.amount_expect), 0).label("amt"))
        .join(Customer, Customer.id == OpportunityProject.customer_id)
        .where(OpportunityProject.tenant_id == tenant_id)
        .group_by(Customer.name).order_by(func.sum(OpportunityProject.amount_expect).desc()).limit(10)
    )).all()
    top_customers = [{"name": r.name, "project_count": r.cnt, "total_amount": float(r.amt)} for r in top_rows]

    # Region
    region_rows = (await db.execute(
        select(Customer.region, func.count(Customer.id).label("count"))
        .where(Customer.tenant_id == tenant_id, Customer.is_deleted == False,
               Customer.region.isnot(None), Customer.region != "")
        .group_by(Customer.region).order_by(func.count(Customer.id).desc())
    )).all()
    regions = [{"region": r.region, "count": r.count} for r in region_rows]

    return {
        "funnel": funnel,
        "won_count": won_count, "lost_count": lost_count,
        "won_amount": won_amount, "lost_amount": lost_amount, "win_rate": win_rate,
        "top_customers": top_customers,
        "regions": regions,
    }


@router.get("/export/excel")
async def export_excel(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    data = await _gather_export_data(db, tenant_id, start_date, end_date)
    wb = Workbook()

    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"),
    )

    def style_header(ws, cols):
        for col_idx, title in enumerate(cols, 1):
            cell = ws.cell(row=1, column=col_idx, value=title)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

    # Sheet 1: Funnel
    ws1 = wb.active
    ws1.title = "销售漏斗"
    style_header(ws1, ["阶段", "名称", "商机数", "金额"])
    for i, f in enumerate(data["funnel"], 2):
        ws1.cell(row=i, column=1, value=f["stage"])
        ws1.cell(row=i, column=2, value=f["label"])
        ws1.cell(row=i, column=3, value=f["count"])
        ws1.cell(row=i, column=4, value=f["amount"])
    ws1.column_dimensions["A"].width = 10
    ws1.column_dimensions["B"].width = 16
    ws1.column_dimensions["C"].width = 12
    ws1.column_dimensions["D"].width = 16

    # Sheet 2: Win/Loss
    ws2 = wb.create_sheet("赢单分析")
    style_header(ws2, ["指标", "值"])
    for i, (k, v) in enumerate([
        ("赢单数", data["won_count"]), ("丢单数", data["lost_count"]),
        ("赢单金额", data["won_amount"]), ("丢单金额", data["lost_amount"]),
        ("赢单率(%)", data["win_rate"]),
    ], 2):
        ws2.cell(row=i, column=1, value=k)
        ws2.cell(row=i, column=2, value=v)
    ws2.column_dimensions["A"].width = 16
    ws2.column_dimensions["B"].width = 16

    # Sheet 3: Top Customers
    ws3 = wb.create_sheet("客户TOP10")
    style_header(ws3, ["排名", "客户名称", "商机数", "总金额"])
    for i, c in enumerate(data["top_customers"], 2):
        ws3.cell(row=i, column=1, value=i - 1)
        ws3.cell(row=i, column=2, value=c["name"])
        ws3.cell(row=i, column=3, value=c["project_count"])
        ws3.cell(row=i, column=4, value=c["total_amount"])
    ws3.column_dimensions["A"].width = 8
    ws3.column_dimensions["B"].width = 24
    ws3.column_dimensions["C"].width = 12
    ws3.column_dimensions["D"].width = 16

    # Sheet 4: Region
    ws4 = wb.create_sheet("区域分布")
    style_header(ws4, ["区域", "客户数"])
    for i, r in enumerate(data["regions"], 2):
        ws4.cell(row=i, column=1, value=r["region"])
        ws4.cell(row=i, column=2, value=r["count"])
    ws4.column_dimensions["A"].width = 20
    ws4.column_dimensions["B"].width = 12

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"analytics_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf")
async def export_pdf(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # Try to register a Chinese font; fall back to Helvetica
    font_name = "Helvetica"
    for font_path in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("CJK", font_path))
                font_name = "CJK"
                break
            except Exception:
                continue

    data = await _gather_export_data(db, tenant_id, start_date, end_date)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=15 * mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title_CJK", parent=styles["Title"], fontName=font_name, fontSize=18)
    h2_style = ParagraphStyle("H2_CJK", parent=styles["Heading2"], fontName=font_name, fontSize=13, spaceAfter=6)
    normal_style = ParagraphStyle("Normal_CJK", parent=styles["Normal"], fontName=font_name, fontSize=9)

    elements = []
    period = ""
    if start_date and end_date:
        period = f"  ({start_date} ~ {end_date})"
    elements.append(Paragraph(f"Analytics Report{period}", title_style))
    elements.append(Spacer(1, 8 * mm))

    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FC")]),
    ])

    # Funnel
    elements.append(Paragraph("Sales Funnel", h2_style))
    t_data = [["Stage", "Label", "Count", "Amount"]]
    for f in data["funnel"]:
        t_data.append([f["stage"], f["label"], str(f["count"]), f"{f['amount']:,.0f}"])
    t = Table(t_data, colWidths=[60, 80, 60, 90])
    t.setStyle(table_style)
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))

    # Win/Loss
    elements.append(Paragraph("Win/Loss Analysis", h2_style))
    t_data = [["Metric", "Value"]]
    t_data.append(["Won", f"{data['won_count']} ({data['won_amount']:,.0f})"])
    t_data.append(["Lost", f"{data['lost_count']} ({data['lost_amount']:,.0f})"])
    t_data.append(["Win Rate", f"{data['win_rate']}%"])
    t = Table(t_data, colWidths=[100, 150])
    t.setStyle(table_style)
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))

    # Top Customers
    elements.append(Paragraph("Top Customers", h2_style))
    t_data = [["#", "Customer", "Projects", "Amount"]]
    for i, c in enumerate(data["top_customers"], 1):
        t_data.append([str(i), c["name"], str(c["project_count"]), f"{c['total_amount']:,.0f}"])
    t = Table(t_data, colWidths=[30, 160, 60, 90])
    t.setStyle(table_style)
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))

    # Region
    if data["regions"]:
        elements.append(Paragraph("Customer Region Distribution", h2_style))
        t_data = [["Region", "Count"]]
        for r in data["regions"]:
            t_data.append([r["region"], str(r["count"])])
        t = Table(t_data, colWidths=[150, 80])
        t.setStyle(table_style)
        elements.append(t)

    doc.build(elements)
    buf.seek(0)
    filename = f"analytics_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- Global Search ---

@router.get("/search")
async def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Search across customers, leads, projects, contacts, and tickets."""
    from app.domains.customer.models import Contact as ContactModel
    pattern = f"%{q}%"
    results = []

    # Customers
    customers = (await db.execute(
        select(Customer.id, Customer.name, Customer.industry, Customer.region)
        .where(Customer.tenant_id == tenant_id, Customer.is_deleted == False,
               or_(Customer.name.ilike(pattern), Customer.short_name.ilike(pattern), Customer.customer_code.ilike(pattern)))
        .limit(5)
    )).all()
    for c in customers:
        results.append({"type": "customer", "id": c.id, "title": c.name,
                        "subtitle": " · ".join(filter(None, [c.industry, c.region])),
                        "url": f"/customers/{c.id}"})

    # Leads
    leads = (await db.execute(
        select(Lead.id, Lead.company_name, Lead.contact_name, Lead.source)
        .where(Lead.tenant_id == tenant_id, Lead.is_deleted == False,
               or_(Lead.company_name.ilike(pattern), Lead.contact_name.ilike(pattern)))
        .limit(5)
    )).all()
    for l in leads:
        results.append({"type": "lead", "id": l.id, "title": l.company_name or l.contact_name,
                        "subtitle": l.contact_name or "",
                        "url": f"/leads/{l.id}"})

    # Projects
    projects = (await db.execute(
        select(OpportunityProject.id, OpportunityProject.name, OpportunityProject.stage_code, OpportunityProject.status)
        .where(OpportunityProject.tenant_id == tenant_id, OpportunityProject.is_deleted == False,
               OpportunityProject.name.ilike(pattern))
        .limit(5)
    )).all()
    for p in projects:
        results.append({"type": "project", "id": p.id, "title": p.name,
                        "subtitle": f"{p.stage_code} · {p.status}",
                        "url": f"/opportunities/{p.id}"})

    # Contacts
    contacts = (await db.execute(
        select(ContactModel.id, ContactModel.name, ContactModel.customer_id, ContactModel.title)
        .where(ContactModel.tenant_id == tenant_id,
               or_(ContactModel.name.ilike(pattern), ContactModel.phone.ilike(pattern), ContactModel.email.ilike(pattern)))
        .limit(5)
    )).all()
    for c in contacts:
        results.append({"type": "contact", "id": c.id, "title": c.name,
                        "subtitle": c.title or "",
                        "url": f"/customers/{c.customer_id}"})

    # Tickets
    tickets = (await db.execute(
        select(ServiceTicket.id, ServiceTicket.ticket_no, ServiceTicket.description, ServiceTicket.status)
        .where(ServiceTicket.tenant_id == tenant_id,
               or_(ServiceTicket.ticket_no.ilike(pattern), ServiceTicket.description.ilike(pattern)))
        .limit(5)
    )).all()
    for t in tickets:
        results.append({"type": "ticket", "id": t.id, "title": t.ticket_no,
                        "subtitle": (t.description or "")[:60],
                        "url": f"/service-tickets"})

    return ok(results)


# --- Win Forecast ---

STAGE_PROBABILITIES = {"S1": 0.10, "S2": 0.20, "S3": 0.40, "S4": 0.60, "S5": 0.80, "S6": 0.95}


@router.get("/win_forecast")
async def win_forecast(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Calculate weighted pipeline forecast by stage."""
    projects = (await db.execute(
        select(
            OpportunityProject.stage_code,
            func.count(OpportunityProject.id).label("count"),
            func.coalesce(func.sum(OpportunityProject.amount_expect), 0).label("total"),
        ).where(
            OpportunityProject.tenant_id == tenant_id,
            OpportunityProject.is_deleted == False,
            OpportunityProject.status == "active",
        ).group_by(OpportunityProject.stage_code)
    )).all()

    stages = []
    weighted_total = 0.0
    pipeline_total = 0.0
    for row in projects:
        prob = STAGE_PROBABILITIES.get(row.stage_code, 0.5)
        amount = float(row.total or 0)
        weighted = amount * prob
        weighted_total += weighted
        pipeline_total += amount
        stages.append({
            "stage": row.stage_code,
            "count": row.count,
            "amount": amount,
            "probability": prob,
            "weighted_amount": round(weighted, 2),
        })

    return ok({
        "stages": sorted(stages, key=lambda x: x["stage"]),
        "pipeline_total": round(pipeline_total, 2),
        "weighted_total": round(weighted_total, 2),
    })


@router.get("/rate_limit_stats")
async def rate_limit_stats(
    _user=Depends(require_permissions("role:manage")),
):
    """Return rate limiter stats for admin dashboard."""
    try:
        from app.middleware.rate_limiter import RateLimitMiddleware
        from app.main import app as fastapi_app
        current = fastapi_app
        for _ in range(20):
            if isinstance(current, RateLimitMiddleware):
                return ok(current.get_stats())
            current = getattr(current, "app", None)
            if current is None:
                break
        return ok({"rpm_limit": 120, "active_clients": 0, "total_rejected": 0, "clients": []})
    except Exception:
        return ok({"rpm_limit": 120, "active_clients": 0, "total_rejected": 0, "clients": []})


@router.get("/stage_duration")
async def stage_duration(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Analyze average time spent in each project stage."""
    from app.domains.project.models import ProjectStageHistory
    from collections import defaultdict

    rows = (await db.execute(
        select(ProjectStageHistory).where(
            ProjectStageHistory.tenant_id == tenant_id,
        ).order_by(ProjectStageHistory.project_id, ProjectStageHistory.created_at)
    )).scalars().all()

    projects: dict[str, list] = defaultdict(list)
    for r in rows:
        projects[r.project_id].append(r)

    stage_durations: dict[str, list[float]] = defaultdict(list)
    for pid, transitions in projects.items():
        for i, t in enumerate(transitions):
            entered = t.created_at
            if i + 1 < len(transitions):
                exited = transitions[i + 1].created_at
            else:
                exited = datetime.now(timezone.utc)
            days = (exited - entered).total_seconds() / 86400
            stage_durations[t.to_stage].append(days)

    stages = []
    for stage in ["S1", "S2", "S3", "S4", "S5", "S6"]:
        durations = stage_durations.get(stage, [])
        if durations:
            stages.append({
                "stage": stage,
                "avg_days": round(sum(durations) / len(durations), 1),
                "min_days": round(min(durations), 1),
                "max_days": round(max(durations), 1),
                "count": len(durations),
            })
        else:
            stages.append({"stage": stage, "avg_days": 0, "min_days": 0, "max_days": 0, "count": 0})

    return ok(stages)


# --- Sales Targets ---

@router.get("/targets")
async def list_targets(
    year: int = Query(..., ge=2020),
    month: int | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dashboard:view")),
):
    q = select(SalesTarget).where(SalesTarget.tenant_id == tenant_id, SalesTarget.year == year)
    if month is not None:
        q = q.where(SalesTarget.month == month)
    items = (await db.execute(q.order_by(SalesTarget.month, SalesTarget.user_name))).scalars().all()
    return ok([{
        "id": t.id, "user_id": t.user_id, "user_name": t.user_name,
        "year": t.year, "month": t.month,
        "target_amount": float(t.target_amount) if t.target_amount else 0,
        "target_count": t.target_count,
    } for t in items])


@router.post("/targets")
async def upsert_target(
    body: dict,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dashboard:view")),
):
    user_id = body.get("user_id", "")
    year = body.get("year", 0)
    month = body.get("month", 0)
    existing = (await db.execute(
        select(SalesTarget).where(
            SalesTarget.tenant_id == tenant_id,
            SalesTarget.user_id == user_id,
            SalesTarget.year == year,
            SalesTarget.month == month,
        )
    )).scalar_one_or_none()

    if existing:
        existing.target_amount = body.get("target_amount", existing.target_amount)
        existing.target_count = body.get("target_count", existing.target_count)
        existing.user_name = body.get("user_name", existing.user_name)
    else:
        t = SalesTarget(
            tenant_id=tenant_id,
            user_id=user_id,
            user_name=body.get("user_name"),
            year=year,
            month=month,
            target_amount=body.get("target_amount", 0),
            target_count=body.get("target_count"),
        )
        db.add(t)
    await db.commit()
    return ok(None)


@router.delete("/targets/{target_id}")
async def delete_target(
    target_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dashboard:view")),
):
    t = (await db.execute(
        select(SalesTarget).where(SalesTarget.tenant_id == tenant_id, SalesTarget.id == target_id)
    )).scalar_one_or_none()
    if t:
        await db.delete(t)
        await db.commit()
    return ok(None)


@router.get("/target_achievement")
async def target_achievement(
    year: int = Query(..., ge=2020),
    month: int | None = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("dashboard:view")),
):
    """Calculate achievement: target vs actual won deals."""
    # Get targets
    tq = select(SalesTarget).where(SalesTarget.tenant_id == tenant_id, SalesTarget.year == year)
    if month:
        tq = tq.where(SalesTarget.month == month)
    targets = (await db.execute(tq)).scalars().all()

    # Get actual won projects in the period
    pq = select(
        OpportunityProject.owner_id,
        func.sum(OpportunityProject.amount_expect).label("total_amount"),
        func.count(OpportunityProject.id).label("total_count"),
    ).where(
        OpportunityProject.tenant_id == tenant_id,
        OpportunityProject.status == "won",
        extract("year", OpportunityProject.updated_at) == year,
    )
    if month:
        pq = pq.where(extract("month", OpportunityProject.updated_at) == month)
    pq = pq.group_by(OpportunityProject.owner_id)
    actuals = {r.owner_id: {"amount": float(r.total_amount or 0), "count": r.total_count or 0}
               for r in (await db.execute(pq)).all()}

    # Merge
    user_map: dict[str, dict] = {}
    for t in targets:
        entry = user_map.setdefault(t.user_id, {
            "user_id": t.user_id, "user_name": t.user_name or "",
            "target_amount": 0, "target_count": 0,
            "actual_amount": 0, "actual_count": 0, "achievement_rate": 0,
        })
        entry["target_amount"] += float(t.target_amount or 0)
        entry["target_count"] += t.target_count or 0

    for uid, data in actuals.items():
        entry = user_map.setdefault(uid, {
            "user_id": uid, "user_name": "",
            "target_amount": 0, "target_count": 0,
            "actual_amount": 0, "actual_count": 0, "achievement_rate": 0,
        })
        entry["actual_amount"] = data["amount"]
        entry["actual_count"] = data["count"]

    for entry in user_map.values():
        if entry["target_amount"] > 0:
            entry["achievement_rate"] = round(entry["actual_amount"] / entry["target_amount"] * 100)

    return ok(list(user_map.values()))


# ── Dashboard Snapshot Sharing ─────────────────────────────────────

class SnapshotCreate(BaseModel):
    title: str = Field(..., max_length=200)
    snapshot_data: dict
    card_visibility: Optional[dict] = None
    card_order: Optional[list] = None
    expires_hours: Optional[int] = None  # None = never expires


@router.post("/snapshots")
async def create_snapshot(
    body: SnapshotCreate,
    tenant_id: str = Depends(get_tenant_id),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import secrets, json
    from datetime import timedelta

    token = secrets.token_urlsafe(32)
    expires_at = None
    if body.expires_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=body.expires_hours)

    snap = DashboardSnapshot(
        tenant_id=tenant_id,
        share_token=token,
        title=body.title,
        created_by=current_user["sub"],
        created_by_name=current_user.get("real_name") or current_user.get("username", ""),
        snapshot_json=json.dumps(body.snapshot_data, ensure_ascii=False),
        card_visibility_json=json.dumps(body.card_visibility) if body.card_visibility else None,
        card_order_json=json.dumps(body.card_order) if body.card_order else None,
        expires_at=expires_at,
    )
    db.add(snap)
    await db.commit()
    return ok({"id": snap.id, "share_token": token, "expires_at": expires_at.isoformat() if expires_at else None})


@router.get("/snapshots")
async def list_snapshots(
    tenant_id: str = Depends(get_tenant_id),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    rows = (await db.execute(
        select(DashboardSnapshot).where(
            DashboardSnapshot.tenant_id == tenant_id,
            DashboardSnapshot.created_by == current_user["sub"],
        ).order_by(DashboardSnapshot.created_at.desc()).limit(50)
    )).scalars().all()
    return ok([{
        "id": s.id, "title": s.title, "share_token": s.share_token,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
    } for s in rows])


@router.get("/snapshots/{token}")
async def get_snapshot(
    token: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    import json
    from app.common.exceptions import BusinessException

    snap = (await db.execute(
        select(DashboardSnapshot).where(DashboardSnapshot.share_token == token)
    )).scalar_one_or_none()
    if not snap:
        raise BusinessException(code=404, message="快照不存在")
    if snap.expires_at and snap.expires_at < datetime.now(timezone.utc):
        raise BusinessException(code=410, message="快照已过期")

    return ok({
        "id": snap.id,
        "title": snap.title,
        "created_by_name": snap.created_by_name,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
        "snapshot_data": json.loads(snap.snapshot_json),
        "card_visibility": json.loads(snap.card_visibility_json) if snap.card_visibility_json else None,
        "card_order": json.loads(snap.card_order_json) if snap.card_order_json else None,
    })


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.common.exceptions import BusinessException
    snap = (await db.execute(
        select(DashboardSnapshot).where(
            DashboardSnapshot.id == snapshot_id,
            DashboardSnapshot.created_by == current_user["sub"],
        )
    )).scalar_one_or_none()
    if not snap:
        raise BusinessException(code=404, message="快照不存在")
    await db.delete(snap)
    await db.commit()
    return ok(None)
