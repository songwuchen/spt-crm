"""扩展平台 — 仪表盘聚合引擎。

运行时对 lc_form_instance.form_data(JSONB)直接 GROUP BY 聚合(无预物化),服务图表数据。
移植思想自 spt-lowcode aggregation_service。MVP 支持:
- 维度(group by): 表单字段, 日期字段可按 年/月/日 粒度;
- 指标: count / count_distinct / sum / avg / max / min(数值安全转换,非数值计 NULL);
- 过滤: eq/ne/contains/gt/gte/lt/lte。

安全: JSONB key 全部走绑定参数(:p_*),聚合函数名/操作符/粒度均白名单,字段 id 额外校验为标识符。
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BusinessException
from app.common.error_codes import VALIDATION_ERROR

_ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")
_AGG = {"sum", "avg", "max", "min"}
_NUMERIC_RE = r"'^-?[0-9]+(\.[0-9]+)?$'"


def _check_id(fid: str) -> str:
    if not fid or not _ID_RE.match(fid):
        raise BusinessException(code=VALIDATION_ERROR, message=f"非法字段标识: {fid}")
    return fid


def _dim_expr(key_param: str, granularity: str | None) -> str:
    base = f"(form_data ->> :{key_param})"
    if granularity == "year":
        return f"substr({base}, 1, 4)"
    if granularity == "month":
        return f"substr({base}, 1, 7)"
    if granularity == "day":
        # 日期时间字段(YYYY-MM-DD HH:MM:SS)按天分组,避免按时间戳打散
        return f"substr({base}, 1, 10)"
    return base


def _safe_numeric(key_param: str) -> str:
    b = f"(form_data ->> :{key_param})"
    return f"(CASE WHEN nullif({b}, '') ~ {_NUMERIC_RE} THEN {b}::numeric ELSE NULL END)"


async def aggregate(
    db: AsyncSession, tenant_id: str, template_id: str,
    dimensions: list[dict[str, Any]], metrics: list[dict[str, Any]],
    filters: list[dict[str, Any]] | None = None, limit: int = 200,
) -> dict[str, Any]:
    # template_id 走绑定参数(:tpl),无需标识符校验。
    params: dict[str, Any] = {"tenant": tenant_id, "tpl": template_id, "lim": max(1, min(int(limit or 200), 2000))}

    select_parts: list[str] = []
    group_positions: list[str] = []
    dim_keys: list[str] = []
    for i, d in enumerate(dimensions or []):
        fid = _check_id(str(d.get("field_id", "")))
        kp = f"d{i}"
        params[kp] = fid
        gran = d.get("granularity") if d.get("granularity") in ("year", "month", "day") else None
        select_parts.append(f"{_dim_expr(kp, gran)} AS dim_{i}")
        group_positions.append(str(i + 1))
        dim_keys.append(f"dim_{i}")

    metric_keys: list[str] = []
    for j, m in enumerate(metrics or []):
        op = str(m.get("op", "count")).lower()
        alias = f"metric_{j}"
        if op == "count":
            select_parts.append(f"count(*) AS {alias}")
        elif op == "count_distinct":
            fid = _check_id(str(m.get("field_id", "")))
            kp = f"m{j}"; params[kp] = fid
            select_parts.append(f"count(distinct (form_data ->> :{kp})) AS {alias}")
        elif op in _AGG:
            fid = _check_id(str(m.get("field_id", "")))
            kp = f"m{j}"; params[kp] = fid
            select_parts.append(f"{op}({_safe_numeric(kp)}) AS {alias}")
        else:
            raise BusinessException(code=VALIDATION_ERROR, message=f"不支持的聚合: {op}")
        metric_keys.append(alias)

    if not select_parts:
        raise BusinessException(code=VALIDATION_ERROR, message="至少需要一个维度或指标")

    where = ["tenant_id = :tenant", "template_id = :tpl", "is_deleted = false"]
    for k, f in enumerate(filters or []):
        fid = _check_id(str(f.get("field_id", "")))
        op = str(f.get("operator", "eq")).lower()
        fkp = f"f{k}"; fvp = f"fv{k}"
        params[fkp] = fid
        val = f.get("value")
        b = f"(form_data ->> :{fkp})"
        if op == "eq":
            where.append(f"{b} = :{fvp}"); params[fvp] = str(val)
        elif op == "ne":
            where.append(f"{b} <> :{fvp}"); params[fvp] = str(val)
        elif op == "contains":
            where.append(f"{b} ILIKE :{fvp}"); params[fvp] = f"%{val}%"
        elif op in ("gt", "gte", "lt", "lte"):
            sym = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
            where.append(f"{_safe_numeric(fkp)} {sym} :{fvp}"); params[fvp] = float(val)
        else:
            raise BusinessException(code=VALIDATION_ERROR, message=f"不支持的过滤操作: {op}")

    sql = f"SELECT {', '.join(select_parts)} FROM lc_form_instance WHERE {' AND '.join(where)}"
    if group_positions:
        sql += f" GROUP BY {', '.join(group_positions)} ORDER BY {', '.join(group_positions)}"
    sql += " LIMIT :lim"

    rows = (await db.execute(text(sql), params)).mappings().all()
    out_rows = []
    for r in rows:
        row = {}
        for dk in dim_keys:
            row[dk] = r[dk]
        for mk in metric_keys:
            v = r[mk]
            row[mk] = float(v) if v is not None else 0
        out_rows.append(row)
    return {"rows": out_rows, "dimensions": dim_keys, "metrics": metric_keys}
