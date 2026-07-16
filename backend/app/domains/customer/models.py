from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, JSON, Boolean, Integer, Numeric, Date, DateTime
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

    # ===== 商机要素 / 采购意向（BANT 快照，客户早期即可承载「为何是潜在商机」）=====
    intent_level: Mapped[str | None] = mapped_column(String(10))
    # 采购意向类别 A/B/C/D，由 expected_purchase_date 推档（A=3月内…），独立于价值等级 level
    key_contact_id: Mapped[str | None] = mapped_column(String(36))  # 关键人（指向 contacts.id）
    demand: Mapped[str | None] = mapped_column(Text)  # 核心需求
    need_match_level: Mapped[str | None] = mapped_column(String(32))  # 产品与需求匹配程度
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))  # 客户预算
    expected_purchase_date: Mapped[date | None] = mapped_column(Date)  # 预计采购时间
    headcount: Mapped[int | None] = mapped_column(Integer)  # 公司总人数

    # ===== 公司档案增补 =====
    industry_l1: Mapped[str | None] = mapped_column(String(100))  # 一级行业
    industry_l2: Mapped[str | None] = mapped_column(String(100))  # 二级行业
    industry_l3: Mapped[str | None] = mapped_column(String(100))  # 三级行业
    country: Mapped[str | None] = mapped_column(String(50))  # 国家
    postal_code: Mapped[str | None] = mapped_column(String(20))  # 邮政编码
    currency: Mapped[str | None] = mapped_column(String(10))  # 币种（CNY/USD…）

    # ===== 归属 / 审计增补 =====
    department_id: Mapped[str | None] = mapped_column(String(36))  # 所属部门（冗余自负责人，便于按部门统计/查询）
    department_name: Mapped[str | None] = mapped_column(String(100))
    updated_by_id: Mapped[str | None] = mapped_column(String(36))  # 最新修改人
    updated_by_name: Mapped[str | None] = mapped_column(String(100))

    # ===== 跟进 / 公海生命周期（冗余，驱动列表「N天未跟进」展示与自动回收）=====
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)  # 最新活动时间
    last_activity_by_id: Mapped[str | None] = mapped_column(String(36))  # 最新跟进人
    last_activity_by_name: Mapped[str | None] = mapped_column(String(100))
    won_deal_count: Mapped[int] = mapped_column(Integer, default=0)  # 结单商机数（冗余，卡片信任信号）
    pool_id: Mapped[str | None] = mapped_column(String(36), index=True)  # 所属区域公海（NULL=默认公海）
    pool_source: Mapped[str | None] = mapped_column(String(32))
    # 进入公海来源: self_built(自建) / manual_release(手动释放) / auto_recycle(系统回收) / assigned(分配后回收)
    pool_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 进入公海时间

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


class CustomerPool(TenantScopedBase):
    """区域公海：把单一全局公海拆成多个可按区域/团队管理的公海池。
    客户 pool_id 指向此表；NULL 视为默认公海。回收规则可分池覆盖租户级。"""

    __tablename__ = "customer_pools"

    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 公海名称（总部/华东区…）
    description: Mapped[str | None] = mapped_column(String(300))
    region_scope: Mapped[str | None] = mapped_column(String(300))
    # 覆盖的行政区划编码前缀，逗号分隔（如 "31,32,33"）；释放到公海时按客户 region_code 自动归池
    rules_json: Mapped[dict | None] = mapped_column(JSON)
    # 回收规则 {enabled, idle_days:{A,B,C,D}, default_idle_days}；非空则覆盖租户级 pool_rules
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
