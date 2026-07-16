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
    region: Mapped[str | None] = mapped_column(String(200))  # legacy 自由文本，保留做展示回退/兼容
    # 结构化省市区（级联地址）：与 Lead 同构。region_code = 最深选中层级的行政区划编码(GB/T 2260)，
    # 支持层级前缀过滤（选到市即命中全市各区）。名称列用于展示与按省/市分组统计。
    province: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(50))
    district: Mapped[str | None] = mapped_column(String(50))
    region_code: Mapped[str | None] = mapped_column(String(12), index=True)
    address: Mapped[str | None] = mapped_column(String(500))  # 详细地址（门牌/街道等）
    website: Mapped[str | None] = mapped_column(String(300))
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    # 录入人(创建人)：与负责人分家，负责人改派后仍据此判定「本人创建」数据可见性
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[str | None] = mapped_column(String(50))  # A/B/C/D
    status: Mapped[str] = mapped_column(String(50), default="active")  # active / inactive
    tags_json: Mapped[dict | None] = mapped_column(JSON)
    remark: Mapped[str | None] = mapped_column(Text)
    custom_fields_json: Mapped[dict | None] = mapped_column(JSON)
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
    reports_to_id: Mapped[str | None] = mapped_column(String(36))  # parent contact id
    remark: Mapped[str | None] = mapped_column(Text)
    custom_fields_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 扩展平台自定义字段


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
