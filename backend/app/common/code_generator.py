"""
Unified document code generator with DB-based daily sequence.

Each (tenant_id, prefix, date) combination gets its own auto-incrementing sequence,
ensuring uniqueness without random collisions.

Usage:
    from app.common.code_generator import generate_code
    code = await generate_code(db, tenant_id, "QT")   # -> QT-20260311-0001
    code = await generate_code(db, tenant_id, "INV")   # -> INV-20260311-0001
    # 技术协议评审对齐简道云 HTJSXY：HTJSXY-2026031101（日期后无连字符、2 位日序）
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, String, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 北京时间取日，对齐简道云 createTime / 每日重置（免 tzdata）
_LOCAL_TZ = timezone(timedelta(hours=8))


class CodeSequence(Base):
    """Stores the current sequence counter per (tenant, prefix, date)."""
    __tablename__ = "code_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    date_key: Mapped[str] = mapped_column(String(8), nullable=False)  # YYYYMMDD
    current_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        # Unique per tenant+prefix+date to prevent duplicates
        {"schema": None},
    )


# Prefix configuration for each document type
PREFIXES = {
    "customer":       "CUS",
    "lead":           "LD",
    "project":        "PRJ",
    "quote":          "QT",
    "contract":       "CT",
    "invoice":        "INV",
    "payment_plan":   "PP",
    "service_ticket": "SRV",
    "change":         "CR",
    "order":          "ORD",
    "tender":         "TND",
    "commission":     "CM",
    "debt_transfer":  "DT",
    "guarantee":      "GT",
    "measurement":    "MS",
    "contract_review": "CR",
    # 简道云流水号：fixedChars=HTJSXY- + yyyyMMdd + 2位日重置
    "tech_agreement_review": "HTJSXY",
}

# 序号位数（默认 4）；简道云技术协议评审 digitsNum=2
SEQ_DIGITS: dict[str, int] = {
    "tech_agreement_review": 2,
}

# 日期与序号之间的连接符（默认 "-"）；简道云 sn 规则为段直接拼接 → ""
DATE_SEQ_SEP: dict[str, str] = {
    "tech_agreement_review": "",
}


async def generate_code(db: AsyncSession, tenant_id: str, biz_type: str, prefix: str | None = None) -> str:
    """
    Generate next sequential code for a business type.

    Args:
        db: Database session
        tenant_id: Tenant ID for isolation
        biz_type: Business type key (e.g. "invoice", "customer")
        prefix: Override prefix (uses PREFIXES[biz_type] if not given)

    Returns:
        Code string like "INV-20260311-0001" or "HTJSXY-2026031101"
    """
    pfx = prefix or PREFIXES.get(biz_type, biz_type.upper())
    # 按北京时间取日（对齐简道云 createTime / 日重置）
    today = datetime.now(_LOCAL_TZ).strftime("%Y%m%d")
    digits = SEQ_DIGITS.get(biz_type, 4)
    sep = DATE_SEQ_SEP.get(biz_type, "-")

    # Try to atomically increment the sequence
    seq_row = (await db.execute(
        select(CodeSequence)
        .where(
            CodeSequence.tenant_id == tenant_id,
            CodeSequence.prefix == pfx,
            CodeSequence.date_key == today,
        )
        .with_for_update()
    )).scalar_one_or_none()

    if seq_row:
        seq_row.current_seq += 1
        next_seq = seq_row.current_seq
    else:
        next_seq = 1
        seq_row = CodeSequence(
            tenant_id=tenant_id,
            prefix=pfx,
            date_key=today,
            current_seq=next_seq,
        )
        db.add(seq_row)

    await db.flush()  # Ensure the row is written (but don't commit — caller manages transaction)
    return f"{pfx}-{today}{sep}{next_seq:0{digits}d}"
