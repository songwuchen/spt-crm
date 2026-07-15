"""流水号(auto_number)生成引擎。

移植自 spt-lowcode app/utils/serial_number.py,适配 CRM:
- 计数行存于 lc_serial_counter(tenant_id 显式传入,而非 context var);
- period_type 折叠进 period_key(每字段仅一条 counter 规则,(租户,模板,字段,周期key) 唯一足够)。

规则模型 props.serial_rules(有序数组,输出顺序=数组顺序,直接拼接):
- {"type":"counter","digits":5,"fixed":true,"reset_period":"none|daily|monthly|yearly","initial_value":1}
- {"type":"date","format":"yyyyMMdd"}  提交日期
- {"type":"text","value":"RK"}          固定字符
- {"type":"field","field_id":"xxx"}     引用其它字段填写内容
旧版 props {prefix,digits} 无 serial_rules 时按 {prefix}-{yyyyMMdd}-{seq}(每日重置)兼容生成。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid

# 中国无夏令时,固定 UTC+8 即等价 Asia/Shanghai,免 tzdata 依赖(Windows 无系统 tz 库)。
LOCAL_TZ = timezone(timedelta(hours=8))


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def format_serial_date(fmt: str, dt: datetime) -> str:
    """按简道云日期记号渲染: y=年 M=月 d=日,连续同字母为一组,其余字符原样保留。"""
    out: list[str] = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch in ("y", "M", "d"):
            j = i
            while j < len(fmt) and fmt[j] == ch:
                j += 1
            n = j - i
            if ch == "y":
                out.append(str(dt.year) if n >= 4 else str(dt.year % 100).zfill(2))
            elif ch == "M":
                out.append(str(dt.month).zfill(2) if n >= 2 else str(dt.month))
            else:
                out.append(str(dt.day).zfill(2) if n >= 2 else str(dt.day))
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def period_key_for(period_type: str, dt: datetime) -> str:
    if period_type == "daily":
        return dt.strftime("%Y-%m-%d")
    if period_type == "monthly":
        return dt.strftime("%Y-%m")
    if period_type == "yearly":
        return dt.strftime("%Y")
    return ""


def normalize_serial_rules(props: dict[str, Any] | None) -> list[dict[str, Any]]:
    """取出规则数组;无 serial_rules 的旧字段(prefix/digits)转等价规则。"""
    props = props or {}
    rules = props.get("serial_rules")
    if isinstance(rules, list) and any((r or {}).get("type") == "counter" for r in rules):
        return [r for r in rules if isinstance(r, dict) and r.get("type")]
    prefix = str(props.get("prefix", "SN"))
    try:
        digits = int(props.get("digits", 5))
    except (TypeError, ValueError):
        digits = 5
    return [
        {"type": "text", "value": f"{prefix}-"},
        {"type": "date", "format": "yyyyMMdd"},
        {"type": "text", "value": "-"},
        {"type": "counter", "digits": digits, "fixed": True, "reset_period": "daily", "initial_value": 1},
    ]


async def next_counter_value(
    db: AsyncSession, tenant_id: str, template_id: str, field_id: str,
    period_key: str, initial_value: int,
) -> int:
    """原子取号: 首条=初始值,已有则 +1。ON CONFLICT 命中唯一索引 uq_lc_serial_counter。"""
    row = (await db.execute(
        text(
            "INSERT INTO lc_serial_counter "
            "(id, tenant_id, template_id, field_id, period_key, current_value, created_at, updated_at) "
            "VALUES (:id, :tenant, :tpl, :fid, :pkey, :initial, now(), now()) "
            "ON CONFLICT (tenant_id, template_id, field_id, period_key) "
            "DO UPDATE SET current_value = lc_serial_counter.current_value + 1, updated_at = now() "
            "RETURNING current_value"
        ),
        {
            "id": generate_uuid(), "tenant": tenant_id, "tpl": template_id,
            "fid": field_id, "pkey": period_key, "initial": initial_value,
        },
    )).scalar_one()
    return int(row)


def _field_value_text(field_id: str, form_data: dict[str, Any], field_defs: list[dict[str, Any]]) -> str:
    value = (form_data or {}).get(field_id)
    if value is None or value == "":
        return ""
    fd = next((f for f in field_defs or [] if f.get("id") == field_id), None)
    if fd and fd.get("type") in ("select", "radio"):
        for opt in fd.get("options") or []:
            if opt.get("value") == value:
                return str(opt.get("label", value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


async def generate_serial_value(
    db: AsyncSession, tenant_id: str, template_id: str,
    field_def: dict[str, Any], form_data: dict[str, Any], field_defs: list[dict[str, Any]],
) -> str:
    """按 serial_rules 生成一条流水号(提交时调用)。"""
    rules = normalize_serial_rules(field_def.get("props"))
    now = local_now()
    parts: list[str] = []
    for rule in rules:
        rtype = rule.get("type")
        if rtype == "counter":
            try:
                digits = max(2, min(12, int(rule.get("digits", 5))))
            except (TypeError, ValueError):
                digits = 5
            try:
                initial = int(rule.get("initial_value", 1))
            except (TypeError, ValueError):
                initial = 1
            period_type = rule.get("reset_period") or "none"
            raw = await next_counter_value(
                db, tenant_id, template_id, str(field_def.get("id")),
                period_key_for(period_type, now), initial,
            )
            num = raw % (10 ** digits)
            parts.append(str(num).zfill(digits) if rule.get("fixed", True) else str(num))
        elif rtype == "date":
            parts.append(format_serial_date(str(rule.get("format") or "yyyyMMdd"), now))
        elif rtype == "text":
            parts.append(str(rule.get("value") or ""))
        elif rtype == "field":
            parts.append(_field_value_text(str(rule.get("field_id") or ""), form_data, field_defs))
    return "".join(parts)


async def generate_serials_for_submit(
    db: AsyncSession, tenant_id: str, template_id: str,
    field_defs: list[dict[str, Any]], form_data: dict[str, Any],
) -> dict[str, Any]:
    """提交链路入口: 为所有值为空的 auto_number 字段生成流水号(编辑/重提保留原值)。"""
    for fd in field_defs or []:
        if fd.get("type") == "auto_number" and not (form_data or {}).get(fd.get("id")):
            form_data[fd["id"]] = await generate_serial_value(db, tenant_id, template_id, fd, form_data, field_defs)
    return form_data
