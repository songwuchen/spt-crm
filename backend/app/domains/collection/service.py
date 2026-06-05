"""应收账龄 + 清欠/抢单 service。

账龄：以「合同应收(amount_total) − 项目已回款(payment_records)」为基础，
     按项目最早合同签订日的账期分桶汇总到客户。
清欠：DebtTransfer 责任移交单 + 抢单(claim) + CollectionFollowUp 催收跟进。
"""
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid, utcnow
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, VALIDATION_ERROR
from app.common.code_generator import generate_code
from app.domains.audit.service import log_action
from app.domains.collection.models import DebtTransfer, CollectionFollowUp
from app.domains.collection.schemas import (
    DebtTransferCreate, DebtTransferUpdate, DebtTransferClaim, CollectionFollowUpCreate,
)

logger = logging.getLogger("spt_crm.collection")

# (low, high_inclusive, key) — high None = open ended
BUCKETS = [(0, 30, "d0_30"), (31, 60, "d31_60"), (61, 90, "d61_90"), (91, 180, "d91_180"), (181, None, "d180p")]


def _bucket(age_days: int) -> str:
    for low, high, key in BUCKETS:
        if age_days >= low and (high is None or age_days <= high):
            return key
    return "d180p"


# ==================== AR Aging ====================
async def aging_report(db: AsyncSession, tenant_id: str):
    from app.domains.contract.models import Contract
    from app.domains.payment.models import PaymentRecord
    from app.domains.project.models import OpportunityProject
    from app.domains.customer.models import Customer

    contract_rows = (await db.execute(
        select(Contract.project_id,
               func.sum(Contract.amount_total).label("total"),
               func.min(Contract.signed_date).label("signed"))
        .where(Contract.tenant_id == tenant_id)
        .group_by(Contract.project_id)
    )).all()

    pay_rows = (await db.execute(
        select(PaymentRecord.project_id, func.sum(PaymentRecord.amount))
        .where(PaymentRecord.tenant_id == tenant_id)
        .group_by(PaymentRecord.project_id)
    )).all()
    paid = {pid: float(s or 0) for pid, s in pay_rows}

    proj_rows = (await db.execute(
        select(OpportunityProject.id, OpportunityProject.customer_id,
               OpportunityProject.owner_id, OpportunityProject.owner_name)
        .where(OpportunityProject.tenant_id == tenant_id)
    )).all()
    proj = {r[0]: (r[1], r[2], r[3]) for r in proj_rows}

    cust_rows = (await db.execute(
        select(Customer.id, Customer.name).where(Customer.tenant_id == tenant_id)
    )).all()
    cust_names = {r[0]: r[1] for r in cust_rows}

    today = date.today()
    per: dict[str, dict] = {}
    bucket_keys = [b[2] for b in BUCKETS]

    for project_id, total, signed in contract_rows:
        total = float(total or 0)
        if not project_id:
            continue
        outstanding = total - paid.get(project_id, 0)
        if outstanding <= 0.005:
            continue
        cust_id, owner_id, owner_name = proj.get(project_id, (None, None, None))
        key = cust_id or "_unlinked"
        agg = per.get(key)
        if agg is None:
            agg = {"customer_id": cust_id, "customer_name": cust_names.get(cust_id, "(未关联客户)"),
                   "owner_id": owner_id, "owner_name": owner_name,
                   "contract_total": 0.0, "received_total": 0.0, "outstanding": 0.0}
            for bk in bucket_keys:
                agg[bk] = 0.0
            per[key] = agg
        age = (today - signed).days if signed else 9999
        bk = _bucket(age)
        agg[bk] += outstanding
        agg["outstanding"] += outstanding
        agg["contract_total"] += total
        agg["received_total"] += paid.get(project_id, 0)

    rows = sorted(per.values(), key=lambda x: x["outstanding"], reverse=True)
    summary = {bk: round(sum(r[bk] for r in rows), 2) for bk in bucket_keys}
    summary["outstanding"] = round(sum(r["outstanding"] for r in rows), 2)
    summary["customer_count"] = len(rows)
    for r in rows:
        for bk in bucket_keys + ["contract_total", "received_total", "outstanding"]:
            r[bk] = round(r[bk], 2)
    return {"summary": summary, "buckets": bucket_keys, "rows": rows}


async def check_overdue_receivables(db: AsyncSession, tenant_id: str) -> int:
    """Notify customer owners of receivables overdue beyond 90 days."""
    from app.domains.notification.service import send_notification
    report = await aging_report(db, tenant_id)
    notified = 0
    for r in report["rows"]:
        overdue = (r.get("d91_180", 0) or 0) + (r.get("d180p", 0) or 0)
        if overdue <= 0 or not r.get("owner_id"):
            continue
        try:
            await send_notification(
                db, tenant_id, recipient_id=r["owner_id"], type="receivable_overdue",
                title=f"应收账款逾期提醒: {r['customer_name']}",
                content=f"客户「{r['customer_name']}」逾期90天以上应收 ¥{overdue:,.2f}，请及时催收。",
                biz_type="customer", biz_id=r.get("customer_id") or "", sender_name="系统",
            )
            notified += 1
        except Exception as e:
            logger.warning("receivable overdue notify failed: %s", e)
    return notified


# ==================== Debt Transfers ====================
async def list_transfers(db, tenant_id, page_no=1, page_size=20, status=None, keyword=None, to_department_id=None):
    base = select(DebtTransfer).where(DebtTransfer.tenant_id == tenant_id)
    if status:
        base = base.where(DebtTransfer.status == status)
    if to_department_id:
        base = base.where(DebtTransfer.to_department_id == to_department_id)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(DebtTransfer.transfer_no.ilike(kw) | DebtTransfer.customer_name.ilike(kw))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(DebtTransfer.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_transfer(db, tenant_id, transfer_id) -> DebtTransfer:
    t = (await db.execute(
        select(DebtTransfer).where(DebtTransfer.id == transfer_id, DebtTransfer.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not t:
        raise BusinessException(code=NOT_FOUND, message="移交单不存在")
    return t


async def create_transfer(db, tenant_id, data: DebtTransferCreate, user: dict) -> DebtTransfer:
    dump = data.model_dump(exclude_unset=True)
    t = DebtTransfer(
        id=generate_uuid(), tenant_id=tenant_id,
        transfer_no=await generate_code(db, tenant_id, "debt_transfer"),
        status="pending",
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **dump,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="debt_transfer", resource_id=t.id,
                     summary=f"创建清欠移交单: {t.transfer_no}")
    return t


async def update_transfer(db, tenant_id, transfer_id, data: DebtTransferUpdate, user: dict) -> DebtTransfer:
    t = await get_transfer(db, tenant_id, transfer_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(t, field, val)
    await db.commit()
    await db.refresh(t)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="debt_transfer", resource_id=t.id,
                     summary=f"更新清欠移交单: {t.transfer_no}")
    return t


async def claim_transfer(db, tenant_id, transfer_id, data: DebtTransferClaim, user: dict) -> DebtTransfer:
    """抢单接收：目标业务员领取，客户责任人随之变更。"""
    t = await get_transfer(db, tenant_id, transfer_id)
    if t.status != "pending":
        raise BusinessException(code=VALIDATION_ERROR, message=f"该移交单状态为「{t.status}」，无法接收")
    name = user.get("real_name") or user.get("username")
    t.status = "claimed"
    t.claimed_by_id = user["sub"]
    t.claimed_by_name = name
    t.claimed_at = utcnow()
    if data.commitment is not None:
        t.commitment = data.commitment
    if data.claimed_department_id:
        t.claimed_department_id = data.claimed_department_id
        t.claimed_department_name = data.claimed_department_name

    # 责任人变更：把客户负责人改为接收人
    if t.customer_id:
        from app.domains.customer.models import Customer
        cust = (await db.execute(
            select(Customer).where(Customer.id == t.customer_id, Customer.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if cust:
            cust.owner_id = user["sub"]
            cust.owner_name = name
        # 时间线记录
        try:
            from app.common.auto_activity import record_activity
            await record_activity(db, tenant_id, "customer", t.customer_id, "system",
                                  f"清欠接单：{name} 接收客户「{t.customer_name}」催收责任", None,
                                  user["sub"], name)
        except Exception as e:
            logger.warning("claim auto-activity failed: %s", e)

    await db.commit()
    await db.refresh(t)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=name,
                     action="update", resource_type="debt_transfer", resource_id=t.id,
                     summary=f"接收清欠移交单: {t.transfer_no}")
    return t


async def withdraw_transfer(db, tenant_id, transfer_id, user: dict) -> DebtTransfer:
    t = await get_transfer(db, tenant_id, transfer_id)
    if t.status != "pending":
        raise BusinessException(code=VALIDATION_ERROR, message="仅待接收的移交单可撤回")
    t.status = "withdrawn"
    await db.commit()
    await db.refresh(t)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="debt_transfer", resource_id=t.id,
                     summary=f"撤回清欠移交单: {t.transfer_no}")
    return t


async def delete_transfer(db, tenant_id, transfer_id, user: dict):
    t = await get_transfer(db, tenant_id, transfer_id)
    await db.delete(t)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="debt_transfer", resource_id=transfer_id,
                     summary=f"删除清欠移交单: {t.transfer_no}")


# ==================== Follow-ups ====================
async def list_followups(db, tenant_id, customer_id=None, transfer_id=None, page_no=1, page_size=50):
    base = select(CollectionFollowUp).where(CollectionFollowUp.tenant_id == tenant_id)
    if customer_id:
        base = base.where(CollectionFollowUp.customer_id == customer_id)
    if transfer_id:
        base = base.where(CollectionFollowUp.transfer_id == transfer_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(CollectionFollowUp.follow_date.desc().nullslast(), CollectionFollowUp.created_at.desc())
        .offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def create_followup(db, tenant_id, data: CollectionFollowUpCreate, user: dict) -> CollectionFollowUp:
    f = CollectionFollowUp(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    if f.customer_id:
        try:
            from app.common.auto_activity import record_activity
            await record_activity(db, tenant_id, "customer", f.customer_id, "note",
                                  f"催收跟进：{f.feedback or ''}"[:200], None,
                                  user["sub"], user.get("real_name") or user.get("username"))
        except Exception as e:
            logger.warning("followup auto-activity failed: %s", e)
    return f
