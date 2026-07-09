"""应收账龄 + 清欠/抢单 service。

账龄：以「合同应收(amount_total) − 项目已回款(payment_records)」为基础，
     按项目最早合同签订日的账期分桶汇总到客户。
清欠：DebtTransfer 责任移交单 + 抢单(claim) + CollectionFollowUp 催收跟进。
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func, case, and_, distinct, literal, String, ARRAY
from sqlalchemy.dialects.postgresql import aggregate_order_by
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


def _f(v) -> float:
    """Decimal/None → 保留 2 位的 float（与原实现的输出类型一致）。"""
    return round(float(v or 0), 2)


# ==================== AR Aging ====================
async def aging_report(db: AsyncSession, tenant_id: str,
                       page_no: int | None = None, page_size: int | None = None):
    """应收账龄报表（按客户聚合）。

    聚合全部下推到 SQL：
      1) 按项目汇总合同应收(min 签订日) 与已回款；
      2) LEFT JOIN 项目/客户，逐项目算应收余额并按账期分桶
         （用签订日阈值区间比较，避免日期相减的类型问题）；
      3) 按客户分组汇总各账龄桶，按应收余额降序。
    summary 始终覆盖全部客户；传入 page_no/page_size 时对客户行做后端分页并返回 total。
    仅统计项目关联的合同（project_id 非空），与原实现范围一致。
    """
    from app.domains.contract.models import Contract
    from app.domains.payment.models import PaymentRecord
    from app.domains.project.models import OpportunityProject
    from app.domains.customer.models import Customer

    bucket_keys = [b[2] for b in BUCKETS]
    today = date.today()

    # 每项目：合同应收合计 + 最早签订日
    contract_agg = (
        select(
            Contract.project_id.label("project_id"),
            func.coalesce(func.sum(Contract.amount_total), 0).label("total"),
            func.min(Contract.signed_date).label("signed"),
        )
        .where(Contract.tenant_id == tenant_id, Contract.project_id.isnot(None))
        .group_by(Contract.project_id)
        .cte("contract_agg")
    )
    # 每项目：已回款合计
    pay_agg = (
        select(
            PaymentRecord.project_id.label("project_id"),
            func.coalesce(func.sum(PaymentRecord.amount), 0).label("paid"),
        )
        .where(PaymentRecord.tenant_id == tenant_id)
        .group_by(PaymentRecord.project_id)
        .cte("pay_agg")
    )

    total_col = contract_agg.c.total
    paid_col = func.coalesce(pay_agg.c.paid, 0)
    outstanding_col = total_col - paid_col
    signed_col = contract_agg.c.signed

    # 账期分桶：age = today - signed。用签订日阈值区间表达按天分桶：
    # 负账期(签订日在未来)与签订日为空都落入 d180p（else 分支）。
    def thr(days: int) -> date:
        return today - timedelta(days=days)
    bucket_col = case(
        (and_(signed_col.isnot(None), signed_col >= thr(30), signed_col <= today), literal("d0_30")),
        (and_(signed_col.isnot(None), signed_col >= thr(60), signed_col <= thr(31)), literal("d31_60")),
        (and_(signed_col.isnot(None), signed_col >= thr(90), signed_col <= thr(61)), literal("d61_90")),
        (and_(signed_col.isnot(None), signed_col >= thr(180), signed_col <= thr(91)), literal("d91_180")),
        else_=literal("d180p"),
    )

    # 逐项目明细行（仅保留仍有应收余额者，与原 outstanding<=0.005 continue 一致）
    proj_line = (
        select(
            func.coalesce(OpportunityProject.customer_id, literal("_unlinked")).label("customer_key"),
            OpportunityProject.customer_id.label("customer_id"),
            Customer.name.label("customer_name"),
            OpportunityProject.owner_id.label("owner_id"),
            OpportunityProject.owner_name.label("owner_name"),
            total_col.label("total"),
            paid_col.label("paid"),
            outstanding_col.label("outstanding"),
            bucket_col.label("bucket"),
        )
        .select_from(
            contract_agg
            .outerjoin(OpportunityProject, and_(
                OpportunityProject.id == contract_agg.c.project_id,
                OpportunityProject.tenant_id == tenant_id,
            ))
            .outerjoin(pay_agg, pay_agg.c.project_id == contract_agg.c.project_id)
            .outerjoin(Customer, and_(
                Customer.id == OpportunityProject.customer_id,
                Customer.tenant_id == tenant_id,
            ))
        )
        .where(outstanding_col > 0.005)
        .cte("proj_line")
    )

    def bucket_sum(bk: str):
        return func.coalesce(
            func.sum(case((proj_line.c.bucket == bk, proj_line.c.outstanding), else_=0)), 0
        )

    # 汇总：覆盖全部客户，不受分页影响
    summary_row = (await db.execute(
        select(
            *[bucket_sum(bk).label(bk) for bk in bucket_keys],
            func.coalesce(func.sum(proj_line.c.outstanding), 0).label("outstanding"),
            func.count(distinct(proj_line.c.customer_key)).label("customer_count"),
        )
    )).mappings().one()
    summary = {bk: _f(summary_row[bk]) for bk in bucket_keys}
    summary["outstanding"] = _f(summary_row["outstanding"])
    summary["customer_count"] = int(summary_row["customer_count"] or 0)

    # 客户负责人：取应收余额最大的项目，array_agg 同序保证 id/name 同源
    owner_id_col = func.array_agg(
        aggregate_order_by(proj_line.c.owner_id, proj_line.c.outstanding.desc()),
        type_=ARRAY(String),
    )[1]
    owner_name_col = func.array_agg(
        aggregate_order_by(proj_line.c.owner_name, proj_line.c.outstanding.desc()),
        type_=ARRAY(String),
    )[1]

    rows_q = (
        select(
            func.max(proj_line.c.customer_id).label("customer_id"),
            func.coalesce(func.max(proj_line.c.customer_name), literal("(未关联客户)")).label("customer_name"),
            owner_id_col.label("owner_id"),
            owner_name_col.label("owner_name"),
            func.coalesce(func.sum(proj_line.c.total), 0).label("contract_total"),
            func.coalesce(func.sum(proj_line.c.paid), 0).label("received_total"),
            func.coalesce(func.sum(proj_line.c.outstanding), 0).label("outstanding"),
            *[bucket_sum(bk).label(bk) for bk in bucket_keys],
        )
        .group_by(proj_line.c.customer_key)
        # customer_key 作次序稳定的 tiebreaker，保证分页不重不漏
        .order_by(func.sum(proj_line.c.outstanding).desc(), proj_line.c.customer_key)
    )
    paginated = page_no is not None and page_size is not None
    if paginated:
        rows_q = rows_q.offset((page_no - 1) * page_size).limit(page_size)

    money_keys = bucket_keys + ["contract_total", "received_total", "outstanding"]
    rows = []
    for r in (await db.execute(rows_q)).mappings().all():
        row = {
            "customer_id": r["customer_id"],
            "customer_name": r["customer_name"],
            "owner_id": r["owner_id"],
            "owner_name": r["owner_name"],
        }
        for k in money_keys:
            row[k] = _f(r[k])
        rows.append(row)

    result = {"summary": summary, "buckets": bucket_keys, "rows": rows}
    if paginated:
        result["total"] = summary["customer_count"]
    return result


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
async def list_transfers(db, tenant_id, page_no=1, page_size=20, status=None, keyword=None, to_department_id=None,
                         adv_filter=None, sort_by=None, sort_order=None, current_user=None):
    base = select(DebtTransfer).where(DebtTransfer.tenant_id == tenant_id)
    if status:
        base = base.where(DebtTransfer.status == status)
    if to_department_id:
        base = base.where(DebtTransfer.to_department_id == to_department_id)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(DebtTransfer.transfer_no.ilike(kw) | DebtTransfer.customer_name.ilike(kw))

    # 高级筛选（多字段/多条件）
    from app.common.search import filter_clause_or_400, resolve_sort
    clause = filter_clause_or_400("collection", adv_filter, {"user_id": (current_user or {}).get("sub")})
    if clause is not None:
        base = base.where(clause)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    order = resolve_sort("collection", sort_by, sort_order, DebtTransfer.created_at.desc())
    items = (await db.execute(
        base.order_by(order).offset((page_no - 1) * page_size).limit(page_size)
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
