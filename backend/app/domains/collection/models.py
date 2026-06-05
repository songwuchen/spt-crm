from sqlalchemy import String, Text, Numeric, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class DebtTransfer(TenantScopedBase):
    """客户责任移交 / 清欠流转单（含"抢单"接收）。

    对应简道云「客户转换部门 + 销售经理抢单」：欠款客户在部门/责任人间移交，
    目标部门业务员在截止前 claim（抢单）接收，带承诺与考核日期。
    """
    __tablename__ = "debt_transfers"

    transfer_no: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(300))
    # 移交类型：销售转清欠 / 清欠转回销售 / 转法务 / 部门间 / 财务转诉讼
    transfer_type: Mapped[str] = mapped_column(String(32), default="sales_to_collection")
    from_department_id: Mapped[str | None] = mapped_column(String(36))
    from_department_name: Mapped[str | None] = mapped_column(String(100))
    from_owner_id: Mapped[str | None] = mapped_column(String(36))
    from_owner_name: Mapped[str | None] = mapped_column(String(100))
    # 目标部门（进入待接单池）
    to_department_id: Mapped[str | None] = mapped_column(String(36), index=True)
    to_department_name: Mapped[str | None] = mapped_column(String(100))
    debt_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    contact: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    debt_note: Mapped[str | None] = mapped_column(Text)  # 欠款说明
    reason: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[str | None] = mapped_column(Date)       # 接收截止
    assess_date: Mapped[str | None] = mapped_column(Date)    # 考核日期
    commitment: Mapped[str | None] = mapped_column(Text)     # 承诺（接收时填写）
    # pending(待接收) / claimed(已接收) / withdrawn(已撤回) / done(已完成) / rejected
    status: Mapped[str] = mapped_column(String(16), default="pending")
    claimed_by_id: Mapped[str | None] = mapped_column(String(36))
    claimed_by_name: Mapped[str | None] = mapped_column(String(100))
    claimed_department_id: Mapped[str | None] = mapped_column(String(36))
    claimed_department_name: Mapped[str | None] = mapped_column(String(100))
    claimed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class CollectionFollowUp(TenantScopedBase):
    """催收跟进记录（对应简道云应收清欠流程的催收信息）。"""
    __tablename__ = "collection_followups"

    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(300))
    transfer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    follow_date: Mapped[str | None] = mapped_column(Date)
    method: Mapped[str | None] = mapped_column(String(32))   # phone/onsite/letter/other
    feedback: Mapped[str | None] = mapped_column(Text)        # 客户反馈
    expected_date: Mapped[str | None] = mapped_column(Date)   # 预计收款时间
    amount_promised: Mapped[float | None] = mapped_column(Numeric(18, 2))
    next_action: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
