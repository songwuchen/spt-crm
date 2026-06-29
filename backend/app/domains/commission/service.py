"""业务提成/奖金核算 service。

核心：回款驱动的提成计算。
  净额    = 合同额 - (运费 + 服务费 + 招待费 + 返还款)
  结算比例 = min(累计回款 / 合同额, 1)
  应计奖金 = 净额 * 提成比例 * 结算比例
  本次可提 = max(应计奖金 - 已提奖金, 0)
"""
import logging
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND
from app.common.code_generator import generate_code
from app.domains.audit.service import log_action
from app.domains.commission.models import CommissionRecord, CommissionRule, CommissionPayout
from app.domains.commission.schemas import (
    CommissionRecordCreate, CommissionRecordUpdate, CommissionPayoutCreate,
    CommissionRuleCreate, CommissionRuleUpdate,
)

logger = logging.getLogger("spt_crm.commission")

D = lambda v: Decimal(str(v or 0))  # noqa: E731


def compute(rec: CommissionRecord) -> None:
    """Recompute settle_rate / accrued_amount / current_amount in place."""
    contract = D(rec.contract_amount)
    deductions = D(rec.deduction_freight) + D(rec.deduction_service) + D(rec.deduction_entertain) + D(rec.deduction_rebate)
    net = contract - deductions
    if net < 0:
        net = Decimal(0)
    received = D(rec.received_amount)
    settle = (received / contract) if contract > 0 else Decimal(0)
    if settle > 1:
        settle = Decimal(1)
    if getattr(rec, "commission_mode", "rate") == "amount":
        # 固定金额模式：应计奖金 = 提成金额 × 回款结算比例（与「回款驱动」一致）
        accrued = (D(rec.commission_amount) * settle).quantize(Decimal("0.01"))
    else:
        # 比例模式：应计奖金 = 净额 × 提成比例 × 回款结算比例
        accrued = (net * D(rec.commission_rate) * settle).quantize(Decimal("0.01"))
    paid = D(rec.paid_amount)
    current = accrued - paid
    if current < 0:
        current = Decimal(0)
    rec.settle_rate = settle.quantize(Decimal("0.0001"))
    rec.accrued_amount = accrued
    rec.current_amount = current.quantize(Decimal("0.01"))


async def _resolve_commission_rate(db: AsyncSession, tenant_id: str, department_id: str | None, contract_amount: float) -> float:
    """Pick the applicable rule's rate; department-specific wins over global."""
    rules = (await db.execute(
        select(CommissionRule).where(CommissionRule.tenant_id == tenant_id, CommissionRule.enabled == True)
        .order_by(CommissionRule.sort_order)
    )).scalars().all()
    best = None
    for r in rules:
        if r.min_amount and contract_amount < float(r.min_amount):
            continue
        if r.scope_type == "department" and r.department_id and r.department_id == department_id:
            return float(r.rate)
        if r.scope_type == "all" and best is None:
            best = float(r.rate)
    return best or 0.0


# ==================== Records ====================
async def list_records(db, tenant_id, page_no=1, page_size=20, owner_id=None, status=None, keyword=None):
    base = select(CommissionRecord).where(CommissionRecord.tenant_id == tenant_id)
    if owner_id:
        base = base.where(CommissionRecord.owner_id == owner_id)
    if status:
        base = base.where(CommissionRecord.status == status)
    if keyword:
        kw = f"%{keyword}%"
        base = base.where(
            CommissionRecord.record_no.ilike(kw) | CommissionRecord.customer_name.ilike(kw)
            | CommissionRecord.owner_name.ilike(kw)
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(CommissionRecord.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)
    )).scalars().all()
    return items, total


async def get_record(db, tenant_id, record_id) -> CommissionRecord:
    rec = (await db.execute(
        select(CommissionRecord).where(CommissionRecord.id == record_id, CommissionRecord.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rec:
        raise BusinessException(code=NOT_FOUND, message="提成单不存在")
    return rec


async def create_record(db, tenant_id, data: CommissionRecordCreate, user: dict) -> CommissionRecord:
    dump = data.model_dump(exclude_unset=True)
    if not dump.get("record_no"):
        dump["record_no"] = await generate_code(db, tenant_id, "commission")
    # 仅比例模式在未填比例时自动套用提成政策；金额模式按固定金额计提
    if dump.get("commission_mode", "rate") != "amount" and not dump.get("commission_rate"):
        dump["commission_rate"] = await _resolve_commission_rate(
            db, tenant_id, dump.get("department_id"), dump.get("contract_amount", 0))
    rec = CommissionRecord(
        id=generate_uuid(), tenant_id=tenant_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **dump,
    )
    compute(rec)
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="commission", resource_id=rec.id,
                     summary=f"创建提成单: {rec.record_no}")
    return rec


async def update_record(db, tenant_id, record_id, data: CommissionRecordUpdate, user: dict) -> CommissionRecord:
    rec = await get_record(db, tenant_id, record_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(rec, field, val)
    compute(rec)
    await db.commit()
    await db.refresh(rec)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="commission", resource_id=rec.id,
                     summary=f"更新提成单: {rec.record_no}")
    return rec


async def delete_record(db, tenant_id, record_id, user: dict):
    rec = await get_record(db, tenant_id, record_id)
    # cascade payouts
    payouts = (await db.execute(
        select(CommissionPayout).where(CommissionPayout.commission_id == record_id, CommissionPayout.tenant_id == tenant_id)
    )).scalars().all()
    for p in payouts:
        await db.delete(p)
    await db.delete(rec)
    await db.commit()
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="commission", resource_id=record_id,
                     summary=f"删除提成单: {rec.record_no}")


async def recalc_received(db, tenant_id, record_id, user: dict) -> CommissionRecord:
    """Refresh received_amount from the linked project's payment records, then recompute."""
    rec = await get_record(db, tenant_id, record_id)
    if rec.project_id:
        from app.domains.payment.models import PaymentRecord
        total = (await db.execute(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id, PaymentRecord.project_id == rec.project_id)
        )).scalar() or 0
        rec.received_amount = total
    compute(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


async def generate_from_contract(db, tenant_id, contract_id, user: dict) -> CommissionRecord:
    """Create (or return existing) a commission record from a signed contract + its payments."""
    from app.domains.contract.models import Contract
    from app.domains.project.models import OpportunityProject
    from app.domains.payment.models import PaymentRecord

    contract = (await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not contract:
        raise BusinessException(code=NOT_FOUND, message="合同不存在")

    existing = (await db.execute(
        select(CommissionRecord).where(
            CommissionRecord.tenant_id == tenant_id, CommissionRecord.contract_id == contract_id)
    )).scalar_one_or_none()

    proj = (await db.execute(
        select(OpportunityProject).where(
            OpportunityProject.id == contract.project_id, OpportunityProject.tenant_id == tenant_id)
    )).scalar_one_or_none()
    received = (await db.execute(
        select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
            PaymentRecord.tenant_id == tenant_id, PaymentRecord.project_id == contract.project_id)
    )).scalar() or 0

    cust_name = None
    if proj and proj.customer_id:
        from app.domains.customer.models import Customer
        cust = (await db.execute(
            select(Customer).where(Customer.id == proj.customer_id, Customer.tenant_id == tenant_id)
        )).scalar_one_or_none()
        cust_name = cust.name if cust else None

    if existing:
        existing.contract_amount = contract.amount_total or 0
        existing.received_amount = received
        compute(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    rate = await _resolve_commission_rate(
        db, tenant_id, proj.owner_id if proj else None, float(contract.amount_total or 0))
    rec = CommissionRecord(
        id=generate_uuid(), tenant_id=tenant_id,
        record_no=await generate_code(db, tenant_id, "commission"),
        project_id=contract.project_id, contract_id=contract_id,
        customer_id=proj.customer_id if proj else None, customer_name=cust_name,
        owner_id=proj.owner_id if proj else None, owner_name=proj.owner_name if proj else None,
        signed_date=contract.signed_date,
        contract_amount=contract.amount_total or 0, received_amount=received,
        commission_rate=rate, status="draft",
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
    )
    compute(rec)
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="commission", resource_id=rec.id,
                     summary=f"从合同生成提成单: {rec.record_no}")
    return rec


# ==================== Payouts ====================
async def list_payouts(db, tenant_id, record_id):
    return (await db.execute(
        select(CommissionPayout).where(
            CommissionPayout.tenant_id == tenant_id, CommissionPayout.commission_id == record_id)
        .order_by(CommissionPayout.paid_at)
    )).scalars().all()


async def add_payout(db, tenant_id, record_id, data: CommissionPayoutCreate, user: dict) -> CommissionPayout:
    rec = await get_record(db, tenant_id, record_id)
    payout = CommissionPayout(
        id=generate_uuid(), tenant_id=tenant_id, commission_id=record_id,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        **data.model_dump(exclude_unset=True),
    )
    db.add(payout)
    await db.flush()  # ensure this payout is counted exactly once in the rollup
    # roll up paid_amount from all payouts
    total_paid = (await db.execute(
        select(func.coalesce(func.sum(CommissionPayout.amount), 0)).where(
            CommissionPayout.tenant_id == tenant_id, CommissionPayout.commission_id == record_id)
    )).scalar() or 0
    rec.paid_amount = float(total_paid)
    compute(rec)
    if D(rec.paid_amount) >= D(rec.accrued_amount) and D(rec.accrued_amount) > 0:
        rec.status = "paid"
    await db.commit()
    await db.refresh(payout)
    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="commission", resource_id=record_id,
                     summary=f"提成支付 ¥{float(data.amount):,.2f}: {rec.record_no}")
    return payout


# ==================== Summary (台账) ====================
async def summary_by_owner(db, tenant_id):
    rows = (await db.execute(
        select(
            CommissionRecord.owner_id, CommissionRecord.owner_name,
            func.count(CommissionRecord.id).label("cnt"),
            func.coalesce(func.sum(CommissionRecord.contract_amount), 0).label("contract_total"),
            func.coalesce(func.sum(CommissionRecord.received_amount), 0).label("received_total"),
            func.coalesce(func.sum(CommissionRecord.accrued_amount), 0).label("accrued_total"),
            func.coalesce(func.sum(CommissionRecord.paid_amount), 0).label("paid_total"),
            func.coalesce(func.sum(CommissionRecord.current_amount), 0).label("payable_total"),
        ).where(CommissionRecord.tenant_id == tenant_id)
        .group_by(CommissionRecord.owner_id, CommissionRecord.owner_name)
        .order_by(func.coalesce(func.sum(CommissionRecord.accrued_amount), 0).desc())
    )).all()
    return [{
        "owner_id": r.owner_id, "owner_name": r.owner_name or "(未指定)",
        "count": r.cnt,
        "contract_total": float(r.contract_total), "received_total": float(r.received_total),
        "accrued_total": float(r.accrued_total), "paid_total": float(r.paid_total),
        "payable_total": float(r.payable_total),
    } for r in rows]


# ==================== Rules ====================
async def list_rules(db, tenant_id):
    return (await db.execute(
        select(CommissionRule).where(CommissionRule.tenant_id == tenant_id).order_by(CommissionRule.sort_order)
    )).scalars().all()


async def create_rule(db, tenant_id, data: CommissionRuleCreate, user: dict) -> CommissionRule:
    rule = CommissionRule(id=generate_uuid(), tenant_id=tenant_id, **data.model_dump(exclude_unset=True))
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_rule(db, tenant_id, rule_id, data: CommissionRuleUpdate, user: dict) -> CommissionRule:
    rule = (await db.execute(
        select(CommissionRule).where(CommissionRule.id == rule_id, CommissionRule.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rule:
        raise BusinessException(code=NOT_FOUND, message="提成政策不存在")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, val)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db, tenant_id, rule_id, user: dict):
    rule = (await db.execute(
        select(CommissionRule).where(CommissionRule.id == rule_id, CommissionRule.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rule:
        raise BusinessException(code=NOT_FOUND, message="提成政策不存在")
    await db.delete(rule)
    await db.commit()
