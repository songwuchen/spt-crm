from sqlalchemy import String, Text, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Guarantee(TenantScopedBase):
    """保函 / 保证金台账。

    对应简道云「保函 / 保证金管理」+ 合同评审的保函字段。跟踪在保金额、
    到期日与退还状态，到期前提醒，避免应退未退造成资金占用/损失。
    """
    __tablename__ = "guarantees"

    guarantee_no: Mapped[str] = mapped_column(String(64), nullable=False)
    # 类型：履约/预付/质量/投标保证金/履约保证金
    type: Mapped[str] = mapped_column(String(24), default="performance")
    # 方向：我方开出(outgoing) / 我方收取(incoming)
    direction: Mapped[str] = mapped_column(String(16), default="outgoing")
    contract_id: Mapped[str | None] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(300))
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    issuer: Mapped[str | None] = mapped_column(String(200))   # 出具机构/银行
    fee: Mapped[float | None] = mapped_column(Numeric(18, 2))  # 手续费
    rate: Mapped[float | None] = mapped_column(Numeric(8, 4))  # 费率
    effective_date: Mapped[str | None] = mapped_column(Date)
    expiry_date: Mapped[str | None] = mapped_column(Date, index=True)
    return_date: Mapped[str | None] = mapped_column(Date)
    # active(生效中) / returned(已退还) / expired(已逾期) / cancelled
    status: Mapped[str] = mapped_column(String(16), default="active")
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
