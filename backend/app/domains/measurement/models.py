from sqlalchemy import String, Text, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class ServiceMeasurement(TenantScopedBase):
    """售后现场设备实测数据。对应简道云「客户服务记录 / 客服日志」的现场实测指标，
    沉淀为设备运行数据库，支撑设备健康分析与复购预测。
    """
    __tablename__ = "service_measurements"

    record_no: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(300))
    service_date: Mapped[str | None] = mapped_column(Date)
    engineer_id: Mapped[str | None] = mapped_column(String(36))
    engineer_name: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(32))  # 冶金/矿山/煤炭/电厂/化工/砂石骨料/其他
    # 设备铭牌
    equipment_name: Mapped[str | None] = mapped_column(String(200))
    equipment_model: Mapped[str | None] = mapped_column(String(120), index=True)
    product_no: Mapped[str | None] = mapped_column(String(120))
    motor_power_kw: Mapped[float | None] = mapped_column(Numeric(10, 2))
    amplitude_mm: Mapped[float | None] = mapped_column(Numeric(8, 2))
    # 现场实测
    material_name: Mapped[str | None] = mapped_column(String(120))
    layer_thickness_mm: Mapped[float | None] = mapped_column(Numeric(10, 2))
    feed_size_mm: Mapped[float | None] = mapped_column(Numeric(10, 2))
    screen_efficiency: Mapped[float | None] = mapped_column(Numeric(6, 2))   # 筛分效率 %
    throughput_tph: Mapped[float | None] = mapped_column(Numeric(12, 2))     # 处理量 t/h
    source_temp_c: Mapped[float | None] = mapped_column(Numeric(6, 1))       # 振源温度
    ambient_temp_c: Mapped[float | None] = mapped_column(Numeric(6, 1))      # 环境温度
    running_current_a: Mapped[float | None] = mapped_column(Numeric(8, 2))   # 运行电流
    daily_run_hours: Mapped[float | None] = mapped_column(Numeric(5, 1))     # 日运行小时
    # 评价
    service_rating: Mapped[str | None] = mapped_column(String(16))  # 优秀/一般/差
    product_rating: Mapped[str | None] = mapped_column(String(16))  # 满意/一般/不满意
    result_desc: Mapped[str | None] = mapped_column(Text)
    issues: Mapped[str | None] = mapped_column(Text)               # 未解决问题
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(String(36))
    created_by_name: Mapped[str | None] = mapped_column(String(100))
