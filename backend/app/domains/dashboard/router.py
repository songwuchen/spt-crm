from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
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
from app.domains.dashboard.models import SalesTarget

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
    uid = user.id
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
            ServiceTicket.owner_id == uid,
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
