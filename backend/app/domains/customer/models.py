from sqlalchemy import String, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Customer(TenantScopedBase):
    __tablename__ = "customers"

    customer_code: Mapped[str | None] = mapped_column(String(100))  # 可对接ERP编码
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))  # industry_code
    scale_level: Mapped[str | None] = mapped_column(String(50))  # 规模等级
    region: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(300))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[str | None] = mapped_column(String(50))  # A/B/C/D
    status: Mapped[str] = mapped_column(String(50), default="active")  # active / inactive
    tags_json: Mapped[dict | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Contact(TenantScopedBase):
    __tablename__ = "contacts"

    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(100))
    role_type: Mapped[str | None] = mapped_column(String(50))  # decision_maker/influencer/user/finance/procurement
    phone: Mapped[str | None] = mapped_column(String(30))
    mobile: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(default=False)
    remark: Mapped[str | None] = mapped_column(Text)


class CustomerRelation(TenantScopedBase):
    __tablename__ = "customer_relations"

    from_customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    to_customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # parent/subsidiary/affiliate/partner/competitor
    note: Mapped[str | None] = mapped_column(String(500))


class AclShare(TenantScopedBase):
    __tablename__ = "acl_shares"

    biz_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # customer/project/quote/contract
    biz_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    shared_to_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # user/department/role
    shared_to_id: Mapped[str] = mapped_column(String(36), nullable=False)
    shared_to_name: Mapped[str | None] = mapped_column(String(100))
    permission: Mapped[str] = mapped_column(String(16), default="view")
    # view/edit
    shared_by_id: Mapped[str | None] = mapped_column(String(36))
    shared_by_name: Mapped[str | None] = mapped_column(String(100))
