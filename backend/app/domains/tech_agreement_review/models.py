from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class TechAgreementReview(TenantScopedBase):
    """合同技术协议评审 — 对齐简道云销售中心「合同技术协议评审HTJSXY」。"""

    __tablename__ = "tech_agreement_reviews"

    review_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # draft / submitted / approved / rejected
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)

    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    company_name: Mapped[str | None] = mapped_column(String(300))

    applicant_id: Mapped[str | None] = mapped_column(String(36))
    applicant_name: Mapped[str | None] = mapped_column(String(100))
    apply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner_id: Mapped[str | None] = mapped_column(String(36), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(String(36))
    department_name: Mapped[str | None] = mapped_column(String(200))

    industry: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500))
    elec_ctrl: Mapped[str | None] = mapped_column(String(64))
    project_title: Mapped[str | None] = mapped_column(Text)
    has_weight_req: Mapped[str | None] = mapped_column(String(16))
    use_idle_equip: Mapped[str | None] = mapped_column(String(16))
    has_smart: Mapped[str | None] = mapped_column(String(16))
    need_pricing: Mapped[str | None] = mapped_column(String(32))
    sign_basis: Mapped[str | None] = mapped_column(String(500))
    ref_contract_no: Mapped[str | None] = mapped_column(String(200))
    pre_contact: Mapped[str | None] = mapped_column(String(200))
    remark: Mapped[str | None] = mapped_column(Text)
    has_objection: Mapped[str | None] = mapped_column(String(16))

    # 设计审批人员等扩展（design_approver_ids / design_approver_2_ids）
    form_json: Mapped[dict | None] = mapped_column(JSON)

    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
