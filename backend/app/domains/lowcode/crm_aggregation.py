"""仪表盘 — CRM 业务域数据源聚合。

让仪表盘图表化既有 CRM 业务数据(客户/线索/订单...),而不仅是自定义表单数据。
安全: 维度/指标列名来自固定 REGISTRY 白名单(请求只能引用白名单内的 field),
过滤值走绑定参数; 租户隔离 + is_deleted 过滤。数据范围(self/dept)MVP 暂按租户全量。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import VALIDATION_ERROR

# 每个实体: 表名、可分组维度列、可统计指标、所需查看权限。
REGISTRY: dict[str, dict[str, Any]] = {
    "customer": {
        "label": "客户", "table": "customers", "perm": "customer:view",
        "dimensions": [
            {"field": "industry", "label": "行业"},
            {"field": "region", "label": "地区"},
            {"field": "level", "label": "级别"},
            {"field": "scale_level", "label": "规模"},
            {"field": "status", "label": "状态"},
        ],
        "metrics": [{"op": "count", "label": "客户数"}],
    },
    "lead": {
        "label": "线索", "table": "leads", "perm": "lead:view",
        "dimensions": [
            {"field": "source", "label": "来源"},
            {"field": "status", "label": "状态"},
            {"field": "industry", "label": "行业"},
            {"field": "category", "label": "类别"},
        ],
        "metrics": [{"op": "count", "label": "线索数"}],
    },
    "order": {
        "label": "订单", "table": "orders", "perm": "order:view",
        "dimensions": [
            {"field": "status", "label": "状态"},
            {"field": "currency", "label": "币种"},
            {"field": "order_date", "label": "下单日期", "date": True},
        ],
        "metrics": [
            {"op": "count", "label": "订单数"},
            {"op": "sum", "field": "amount", "label": "金额合计"},
        ],
    },
    "opportunity": {
        "label": "商机", "table": "opportunity_projects", "perm": "project:view",
        "dimensions": [
            {"field": "stage_code", "label": "阶段"},
            {"field": "status", "label": "状态"},
            {"field": "risk_level", "label": "风险"},
            {"field": "owner_name", "label": "负责人"},
            {"field": "close_date_expect", "label": "预计成交", "date": True},
        ],
        "metrics": [
            {"op": "count", "label": "商机数"},
            {"op": "sum", "field": "amount_expect", "label": "预计金额"},
            {"op": "avg", "field": "probability", "label": "平均赢率"},
        ],
    },
    "contract": {
        "label": "合同", "table": "contracts", "perm": "contract:view", "soft_delete": False,
        "dimensions": [
            {"field": "status", "label": "状态"},
            {"field": "signed_date", "label": "签约日期", "date": True},
        ],
        "metrics": [
            {"op": "count", "label": "合同数"},
            {"op": "sum", "field": "amount_total", "label": "合同额合计"},
        ],
    },
    "service_ticket": {
        "label": "售后工单", "table": "service_tickets", "perm": "service:view", "soft_delete": False,
        "dimensions": [
            {"field": "type", "label": "类型"},
            {"field": "priority", "label": "优先级"},
            {"field": "status", "label": "状态"},
            {"field": "created_at", "label": "创建日期", "date": True},
        ],
        "metrics": [
            {"op": "count", "label": "工单数"},
            {"op": "avg", "field": "satisfaction_score", "label": "平均满意度"},
        ],
    },
}

_AGG = {"sum", "avg", "max", "min"}


def get_registry() -> list[dict[str, Any]]:
    return [
        {"entity": k, "label": v["label"], "dimensions": v["dimensions"], "metrics": v["metrics"]}
        for k, v in REGISTRY.items()
    ]


def entity_perm(entity: str) -> str | None:
    e = REGISTRY.get(entity)
    return e["perm"] if e else None


def _dim_col(col: str, granularity: str | None, is_date: bool) -> str:
    if is_date and granularity == "year":
        return f"to_char({col}, 'YYYY')"
    if is_date and granularity == "month":
        return f"to_char({col}, 'YYYY-MM')"
    return f"{col}::text"


async def aggregate_crm(
    db: AsyncSession, tenant_id: str, entity: str,
    dimensions: list[dict[str, Any]], metrics: list[dict[str, Any]],
    filters: list[dict[str, Any]] | None = None, limit: int = 200,
) -> dict[str, Any]:
    reg = REGISTRY.get(entity)
    if not reg:
        raise BusinessException(code=VALIDATION_ERROR, message=f"不支持的业务实体: {entity}")
    dim_fields = {d["field"]: d for d in reg["dimensions"]}
    metric_fields = {m.get("field") for m in reg["metrics"] if m.get("field")}

    params: dict[str, Any] = {"tenant": tenant_id, "lim": max(1, min(int(limit or 200), 2000))}
    select_parts: list[str] = []
    group_positions: list[str] = []
    dim_keys: list[str] = []
    for i, d in enumerate(dimensions or []):
        field = d.get("field_id") or d.get("field")
        if field not in dim_fields:
            raise BusinessException(code=VALIDATION_ERROR, message=f"非法维度: {field}")
        gran = d.get("granularity") if d.get("granularity") in ("year", "month") else None
        select_parts.append(f"{_dim_col(field, gran, bool(dim_fields[field].get('date')))} AS dim_{i}")
        group_positions.append(str(i + 1))
        dim_keys.append(f"dim_{i}")

    metric_keys: list[str] = []
    for j, m in enumerate(metrics or []):
        op = str(m.get("op", "count")).lower()
        alias = f"metric_{j}"
        if op == "count":
            select_parts.append(f"count(*) AS {alias}")
        elif op in _AGG:
            field = m.get("field_id") or m.get("field")
            if field not in metric_fields:
                raise BusinessException(code=VALIDATION_ERROR, message=f"非法统计字段: {field}")
            select_parts.append(f"{op}({field}) AS {alias}")
        else:
            raise BusinessException(code=VALIDATION_ERROR, message=f"不支持的聚合: {op}")
        metric_keys.append(alias)

    if not select_parts:
        raise BusinessException(code=VALIDATION_ERROR, message="至少需要一个维度或指标")

    where = ["tenant_id = :tenant"]
    if reg.get("soft_delete", True):
        where.append("is_deleted = false")
    for k, f in enumerate(filters or []):
        field = f.get("field_id") or f.get("field")
        if field not in dim_fields and field not in metric_fields:
            raise BusinessException(code=VALIDATION_ERROR, message=f"非法过滤字段: {field}")
        op = str(f.get("operator", "eq")).lower()
        fvp = f"fv{k}"
        if op == "eq":
            where.append(f"{field}::text = :{fvp}"); params[fvp] = str(f.get("value"))
        elif op == "ne":
            where.append(f"{field}::text <> :{fvp}"); params[fvp] = str(f.get("value"))
        elif op in ("gt", "gte", "lt", "lte"):
            sym = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
            where.append(f"{field} {sym} :{fvp}"); params[fvp] = float(f.get("value"))
        else:
            raise BusinessException(code=VALIDATION_ERROR, message=f"不支持的过滤操作: {op}")

    sql = f"SELECT {', '.join(select_parts)} FROM {reg['table']} WHERE {' AND '.join(where)}"
    if group_positions:
        sql += f" GROUP BY {', '.join(group_positions)} ORDER BY {', '.join(group_positions)}"
    sql += " LIMIT :lim"

    rows = (await db.execute(text(sql), params)).mappings().all()
    out_rows = []
    for r in rows:
        row = {dk: r[dk] for dk in dim_keys}
        for mk in metric_keys:
            v = r[mk]
            row[mk] = float(v) if v is not None else 0
        out_rows.append(row)
    return {"rows": out_rows, "dimensions": dim_keys, "metrics": metric_keys}
