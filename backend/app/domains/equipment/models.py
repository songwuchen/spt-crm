from sqlalchemy import String, Text, Integer, Numeric, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class CustomerEquipment(TenantScopedBase):
    """客户设备台账。对应简道云精细化营销的"设备使用情况/备件使用"。

    标记竞品设备与更换计划，用于识别"使用竞品、临近更换"的客户，生成替换/复购商机。
    """
    __tablename__ = "customer_equipments"

    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(300))
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # 设备名称
    category: Mapped[str | None] = mapped_column(String(64))         # 类型(振动筛/给料机...)
    spec: Mapped[str | None] = mapped_column(String(200))           # 规格型号
    supplier: Mapped[str | None] = mapped_column(String(200))       # 供货厂家
    is_competitor: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # 是否竞品
    usage_years: Mapped[float | None] = mapped_column(Numeric(6, 1))  # 使用年限
    quantity: Mapped[int | None] = mapped_column(Integer)
    condition: Mapped[str | None] = mapped_column(Text)             # 现状描述
    replace_plan_date: Mapped[str | None] = mapped_column(Date, index=True)  # 预计更换时间
    spare_usage: Mapped[str | None] = mapped_column(Text)           # 备件使用情况/更换频率
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))


class CustomerProcessSurvey(TenantScopedBase):
    """客户工艺调研（精细化营销推进流程）。"""
    __tablename__ = "customer_process_surveys"

    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(300))
    industry: Mapped[str | None] = mapped_column(String(64))   # 冶金/焦化/电力/矿山/砂石骨料/煤炭/精细物料
    main_products: Mapped[str | None] = mapped_column(String(300))
    annual_output: Mapped[str | None] = mapped_column(String(100))
    branch_info: Mapped[str | None] = mapped_column(Text)      # 下属分厂情况
    process_desc: Mapped[str | None] = mapped_column(Text)     # 客户工艺文字描述
    pain_points: Mapped[str | None] = mapped_column(Text)
    survey_date: Mapped[str | None] = mapped_column(Date)
    owner_id: Mapped[str | None] = mapped_column(String(36))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
