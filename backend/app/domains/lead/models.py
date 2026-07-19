from sqlalchemy import String, Text, Integer, JSON, Boolean, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Lead(TenantScopedBase):
    __tablename__ = "leads"

    lead_code: Mapped[str | None] = mapped_column(String(64), index=True)
    # 业务日期：用户可自行编辑，用于标识不同时间的线索（区别于系统自动的 created_at）(issue #84)
    biz_date: Mapped[str | None] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(300))
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    contact_raw_json: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(100))  # expo/referral/ad/inbound/partner/call
    source_detail_json: Mapped[dict | None] = mapped_column(JSON)
    demand_summary: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(100))
    customer_type: Mapped[str | None] = mapped_column(String(50))  # DataDictionary(dict_type=customer_type)
    category: Mapped[str | None] = mapped_column(String(20))  # self_reported / distributed
    country_type: Mapped[str | None] = mapped_column(String(20))  # domestic / overseas
    country_name: Mapped[str | None] = mapped_column(String(100))  # only set when country_type=overseas
    region: Mapped[str | None] = mapped_column(String(200))  # legacy free-text, kept for back-compat
    province: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(50))
    district: Mapped[str | None] = mapped_column(String(50))
    # 行政区划编码(GB/T 2260) 最深选中层级，支持层级前缀过滤，与 Customer 同构
    region_code: Mapped[str | None] = mapped_column(String(12), index=True)
    department_id: Mapped[str | None] = mapped_column(String(36))
    budget_range: Mapped[str | None] = mapped_column(String(100))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    # 录入人(创建人)：负责人改派后仍据此判定「本人创建」数据可见性
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="new")  # new / following / qualified / discarded
    # 审核态（提交审核流程）：approved=免审/已通过（默认可用）, pending=待内勤审核, rejected=已驳回。
    # 与 status 正交：status 表达销售进程，review_status 是创建时的审核门禁。
    review_status: Mapped[str] = mapped_column(String(20), default="approved", index=True)
    # 关联的审批流 id。2026-07-19 线索审核切到扩展平台工作流引擎后，新数据存的是
    # wf_process_instance.id；此前的历史数据存的是 approval_flows.id（两者不可混查）。
    review_flow_id: Mapped[str | None] = mapped_column(String(36))
    reject_reason: Mapped[str | None] = mapped_column(Text)  # 最近一次驳回原因
    score: Mapped[int] = mapped_column(Integer, default=0)
    converted_customer_id: Mapped[str | None] = mapped_column(String(36))
    remark: Mapped[str | None] = mapped_column(Text)
    custom_fields_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 扩展平台自定义字段
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class LeadProduct(TenantScopedBase):
    """线索产品信息子表：一条线索可包含多条产品明细(产品名称/规格/数量/备注)(issue #84)。"""
    __tablename__ = "lead_products"

    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    product_name: Mapped[str | None] = mapped_column(String(300))
    product_spec: Mapped[str | None] = mapped_column(String(300))
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 3))
    remark: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int | None] = mapped_column(Integer)
