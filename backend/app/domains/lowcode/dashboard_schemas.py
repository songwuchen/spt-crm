"""扩展平台 — 仪表盘 Pydantic schemas。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DashboardCreate(BaseModel):
    name: str = Field(max_length=128)
    description: str | None = None


class DashboardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    components: list[dict[str, Any]] | None = None
    styles: dict[str, Any] | None = None


class DashboardOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    components: list[dict[str, Any]]
    styles: dict[str, Any]

    model_config = {"from_attributes": True}


class AggDimension(BaseModel):
    field_id: str
    granularity: str | None = None  # year / month / day (日期字段)


class AggMetric(BaseModel):
    op: str = "count"               # count / count_distinct / sum / avg / max / min
    field_id: str | None = None


class AggFilter(BaseModel):
    field_id: str
    operator: str = "eq"            # eq/ne/contains/gt/gte/lt/lte
    value: Any = None


class AggregateRequest(BaseModel):
    template_id: str
    dimensions: list[AggDimension] = Field(default_factory=list)
    metrics: list[AggMetric] = Field(default_factory=list)
    filters: list[AggFilter] = Field(default_factory=list)
    limit: int = 200


class CrmAggregateRequest(BaseModel):
    entity: str                     # customer / lead / order ...
    dimensions: list[AggDimension] = Field(default_factory=list)
    metrics: list[AggMetric] = Field(default_factory=list)
    filters: list[AggFilter] = Field(default_factory=list)
    limit: int = 200
