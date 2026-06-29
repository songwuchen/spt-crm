from sqlalchemy import String, Text, Numeric, Date, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class CommissionRule(TenantScopedBase):
    """提成政策：按部门/产品类型配置提成比例与门槛。"""
    __tablename__ = "commission_rules"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), default="all")  # all/department
    department_id: Mapped[str | None] = mapped_column(String(36), index=True)
    department_name: Mapped[str | None] = mapped_column(String(100))
    rate: Mapped[float] = mapped_column(Numeric(8, 4), default=0)  # 提成比例 0-1
    min_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))  # 起算合同额
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str | None] = mapped_column(Text)


class CommissionRecord(TenantScopedBase):
    """提成单：回款驱动的业务奖金核算。

    应计奖金 = (合同额 - 扣减项合计) * 提成比例 * 结算比例(累计回款/合同额)
    本次可提 = 应计奖金 - 已提奖金
    """
    __tablename__ = "commission_records"

    record_no: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    contract_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(300))
    # 业务员 / 部门
    owner_id: Mapped[str | None] = mapped_column(String(36), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(String(36))
    department_name: Mapped[str | None] = mapped_column(String(100))
    signed_date: Mapped[str | None] = mapped_column(Date)
    # 金额
    contract_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    received_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)  # 累计回款
    deduction_freight: Mapped[float] = mapped_column(Numeric(18, 2), default=0)   # 运费
    deduction_service: Mapped[float] = mapped_column(Numeric(18, 2), default=0)   # 服务费
    deduction_entertain: Mapped[float] = mapped_column(Numeric(18, 2), default=0)  # 招待费
    deduction_rebate: Mapped[float] = mapped_column(Numeric(18, 2), default=0)    # 返还款
    commission_mode: Mapped[str] = mapped_column(String(8), default="rate")       # rate=按比例 / amount=按固定金额
    commission_rate: Mapped[float] = mapped_column(Numeric(8, 4), default=0)      # 提成比例 0-1
    commission_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)   # 固定提成金额(amount 模式)
    # 计算结果
    settle_rate: Mapped[float] = mapped_column(Numeric(8, 4), default=0)          # 结算比例
    accrued_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)      # 应计奖金
    paid_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)         # 已提奖金
    current_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)      # 本次可提
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/submitted/approved/paid
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class CommissionPayout(TenantScopedBase):
    """提成支付明细：支持分次支付。"""
    __tablename__ = "commission_payouts"

    commission_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    paid_at: Mapped[str | None] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    method: Mapped[str | None] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
