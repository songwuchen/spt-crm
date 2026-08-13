"""
Unified document code generator with DB-based sequence.

Each (tenant_id, prefix, date_key) combination gets its own auto-incrementing sequence,
ensuring uniqueness without random collisions.

Usage:
    from app.common.code_generator import generate_code
    code = await generate_code(db, tenant_id, "QT")   # -> QT-20260311-0001
    code = await generate_code(db, tenant_id, "INV")   # -> INV-20260311-0001
    # 技术协议评审对齐简道云 HTJSXY：HTJSXY-2026031101（日期后无连字符、2 位日序）
    # 线索项目号：202608001；商机：PRJ-202608001（年月 + 3 位月序）
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, String, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 北京时间取日/月，对齐简道云 createTime / 周期重置（免 tzdata）
_LOCAL_TZ = timezone(timedelta(hours=8))


class CodeSequence(Base):
    """Stores the current sequence counter per (tenant, prefix, date)."""
    __tablename__ = "code_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    date_key: Mapped[str] = mapped_column(String(8), nullable=False)  # YYYYMMDD 或 YYYYMM
    current_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        # Unique per tenant+prefix+date to prevent duplicates
        {"schema": None},
    )


# Prefix configuration for each document type（空串 = 输出不含字母前缀）
PREFIXES = {
    "customer":       "CUS",
    "lead":           "",  # 项目号：202608001
    "project":        "PRJ",  # 商机：PRJ-202608001（规则同线索，带前缀）
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

# 序号位数（默认 4）；简道云技术协议评审 digitsNum=2；线索/商机项目号 3 位月序
SEQ_DIGITS: dict[str, int] = {
    "tech_agreement_review": 2,
    "lead": 3,
    "project": 3,
}

# 日期与序号之间的连接符（默认 "-"）；简道云 sn / 线索·商机项目号为直接拼接 → ""
DATE_SEQ_SEP: dict[str, str] = {
    "tech_agreement_review": "",
    "lead": "",
    "project": "",
}

# date_key 格式（默认按日 YYYYMMDD）；线索/商机按月 YYYYMM
DATE_KEY_FMT: dict[str, str] = {
    "lead": "%Y%m",
    "project": "%Y%m",
}

# 序列表里空前缀易混淆，线索用内部前缀存计数，输出仍无字母段
_SEQ_PREFIX_ALIAS: dict[str, str] = {
    "lead": "LEAD_YM",
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
        Code string like "INV-20260311-0001"、"HTJSXY-2026031101"、线索 "202608001"、商机 "PRJ-202608001"
    """
    display_pfx = PREFIXES.get(biz_type, biz_type.upper()) if prefix is None else prefix
    seq_pfx = _SEQ_PREFIX_ALIAS.get(biz_type, display_pfx) if prefix is None else prefix
    if not seq_pfx:
        seq_pfx = biz_type.upper() or "DOC"

    date_fmt = DATE_KEY_FMT.get(biz_type, "%Y%m%d")
    date_key = datetime.now(_LOCAL_TZ).strftime(date_fmt)
    digits = SEQ_DIGITS.get(biz_type, 4)
    sep = DATE_SEQ_SEP.get(biz_type, "-")

    seq_row = (await db.execute(
        select(CodeSequence)
        .where(
            CodeSequence.tenant_id == tenant_id,
            CodeSequence.prefix == seq_pfx,
            CodeSequence.date_key == date_key,
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
            prefix=seq_pfx,
            date_key=date_key,
            current_seq=next_seq,
        )
        db.add(seq_row)

    await db.flush()
    body = f"{date_key}{sep}{next_seq:0{digits}d}"
    if display_pfx:
        return f"{display_pfx}-{body}"
    return body
