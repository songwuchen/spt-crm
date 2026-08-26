from sqlalchemy import String, Text, JSON, Integer, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Contract(TenantScopedBase):
    __tablename__ = "contracts"

    # project_id is optional: internally a contract belongs to a project, but
    # contracts ingested through the Open API (e.g. 简道云 合同登记表) are
    # customer-centric and may have no CRM project — mirror the order/tender model.
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    # Direct customer link for externally-sourced contracts (no project chain).
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    contract_no: Mapped[str] = mapped_column(String(64), nullable=False)
    # 简道云 data_id 等外部幂等键：有值时 OpenAPI 按此 upsert，允许同 contract_no 多行
    external_key: Mapped[str | None] = mapped_column(String(128), index=True)
    serial_no: Mapped[str | None] = mapped_column(String(64), index=True)
    from_quote_id: Mapped[str | None] = mapped_column(String(36), index=True)
    current_version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/signed/terminated
    signed_date: Mapped[str | None] = mapped_column(Date)
    end_date: Mapped[str | None] = mapped_column(Date)
    # 简道云合同登记对齐：图纸编号 / 对方合同号 / 获取方式 / 交货期 / 新增|变动
    drawing_no: Mapped[str | None] = mapped_column(String(100), index=True)
    peer_contract_no: Mapped[str | None] = mapped_column(String(100))
    acquire_method: Mapped[str | None] = mapped_column(String(64))
    delivery_date: Mapped[str | None] = mapped_column(Date)
    change_type: Mapped[str | None] = mapped_column(String(16))  # new / change（对应新增/变动）
    # 订货日期 / 下卡日期（简道云登记表）
    order_date: Mapped[str | None] = mapped_column(Date)
    card_date: Mapped[str | None] = mapped_column(Date)
    amount_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    payment_terms_json: Mapped[dict | None] = mapped_column(JSON)
    delivery_terms_json: Mapped[dict | None] = mapped_column(JSON)
    # 简道云合同登记表业务扩展（质保/行业/地址/验收等），详情页按分区展示
    registration_json: Mapped[dict | None] = mapped_column(JSON)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    # 子模块负责人（多部门/多人协作）
    assignee_id: Mapped[str | None] = mapped_column(String(36), index=True)
    assignee_name: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(String(36))
    department_name: Mapped[str | None] = mapped_column(String(100))
    # Tenant-defined extension fields (see custom_field_defs, entity_type="contract").
    custom_fields_json: Mapped[dict | None] = mapped_column(JSON)


class ContractVersion(TenantScopedBase):
    __tablename__ = "contract_versions"

    contract_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    doc_attachment_id: Mapped[str | None] = mapped_column(String(36))
    key_clauses_json: Mapped[dict | None] = mapped_column(JSON)
    risk_level: Mapped[str | None] = mapped_column(String(2))  # L/M/H
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/approved/signed
