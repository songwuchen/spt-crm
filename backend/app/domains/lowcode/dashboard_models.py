"""扩展平台 — 仪表盘数据模型。

移植思想自 spt-lowcode dashboard: 仪表盘 = 组件(图表/指标/表格)数组(JSONB) + 网格布局。
每个组件 {id, type, layout:{x,y,w,h}, config:{data_source, ...}}。图表数据由 AggregationService
在查询时对 lc_form_instance.form_data JSONB 聚合(无预物化)。
"""
from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import TenantScopedBase


class Dashboard(TenantScopedBase):
    __tablename__ = "lc_dashboard"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 组件数组: [{id, type, layout:{x,y,w,h}, config}]
    components: Mapped[list] = mapped_column(JSONB, default=list, nullable=False, server_default="[]")
    # 仪表盘级样式/设置(主题/背景/刷新间隔等)
    styles: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
