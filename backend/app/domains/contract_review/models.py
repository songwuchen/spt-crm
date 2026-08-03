from datetime import datetime
from sqlalchemy import String, Text, Numeric, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class ContractReview(TenantScopedBase):
    """合同评审 — 对齐简道云「合同评审」签约门闸表单。

    列表/检索用一等公民列；其余业务扩展字段落在 review_json（含联系信息子表、六维风险等）。
    """

    __tablename__ = "contract_reviews"

    review_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 合同评审 / 项目评审
    review_type: Mapped[str | None] = mapped_column(String(32))
    # draft / submitted / approved / rejected
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)

    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    company_name: Mapped[str | None] = mapped_column(String(300))

    owner_id: Mapped[str | None] = mapped_column(String(36), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(String(36))
    department_name: Mapped[str | None] = mapped_column(String(200))
    region_manager_id: Mapped[str | None] = mapped_column(String(36))
    region_manager_name: Mapped[str | None] = mapped_column(String(100))

    is_export: Mapped[str | None] = mapped_column(String(16))
    need_pricing: Mapped[str | None] = mapped_column(String(32))
    need_install: Mapped[str | None] = mapped_column(String(64))
    customer_type: Mapped[str | None] = mapped_column(String(32))
    elec_ctrl: Mapped[str | None] = mapped_column(String(64))

    project_title: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contract_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    delivery_period: Mapped[str | None] = mapped_column(String(200))

    conclusion: Mapped[str | None] = mapped_column(Text)
    payment_term: Mapped[str | None] = mapped_column(String(200))

    review_json: Mapped[dict | None] = mapped_column(JSON)
    # 扩展平台「自定义字段 → 合同评审」：值存于此，与原生列 / review_json 分离
    custom_fields_json: Mapped[dict | None] = mapped_column(JSON)

    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
