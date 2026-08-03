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


def _parse_form_date(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=LOCAL_TZ)
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19] if "T" in s or " " in s else s[:10], fmt).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    except ValueError:
        return None


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


async def peek_counter_value(
    db: AsyncSession, tenant_id: str, template_id: str, field_id: str,
    period_key: str, initial_value: int,
) -> int:
    """预览下一号（不落库）。无计数行时返回 initial_value。"""
    row = (await db.execute(
        text(
            "SELECT current_value FROM lc_serial_counter "
            "WHERE tenant_id=:tenant AND template_id=:tpl AND field_id=:fid AND period_key=:pkey"
        ),
        {"tenant": tenant_id, "tpl": template_id, "fid": field_id, "pkey": period_key},
    )).scalar_one_or_none()
    if row is None:
        return initial_value
    return int(row) + 1


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


def _resolve_serial_dt(rule: dict[str, Any], form_data: dict[str, Any], now: datetime) -> datetime:
    date_field = rule.get("date_field")
    if date_field:
        parsed = _parse_form_date((form_data or {}).get(date_field))
        if parsed:
            return parsed
    return now


def _map_by_field(
    by: dict[str, Any] | None, form_data: dict[str, Any], field_defs: list[dict[str, Any]],
) -> str | None:
    """按依赖字段取值查 map：优先表单原始 value，再回退到选项 label。"""
    by = by or {}
    fid = by.get("field_id")
    mapping = by.get("map") or {}
    if not fid or not isinstance(mapping, dict):
        return None
    raw = (form_data or {}).get(fid)
    if raw is not None and raw != "" and str(raw) in mapping:
        return str(mapping[str(raw)])
    label = _field_value_text(str(fid), form_data, field_defs)
    if label in mapping:
        return str(mapping[label])
    return None


def _resolve_date_format(
    rule: dict[str, Any], form_data: dict[str, Any], field_defs: list[dict[str, Any]],
) -> str:
    fmt = str(rule.get("format") or "yyyyMMdd")
    mapped = _map_by_field(rule.get("format_by_field"), form_data, field_defs)
    return mapped if mapped is not None else fmt


def _resolve_reset_period(
    rule: dict[str, Any], form_data: dict[str, Any], field_defs: list[dict[str, Any]],
) -> str:
    mapped = _map_by_field(rule.get("reset_period_by_field"), form_data, field_defs)
    if mapped is not None:
        return mapped
    return str(rule.get("reset_period") or "none")


def _counter_period_key(
    rule: dict[str, Any], form_data: dict[str, Any], field_defs: list[dict[str, Any]], dt: datetime,
) -> str:
    """周期 key：可选拼上依赖字段(如编号属性)，使 WMGF/SY 分序列。"""
    period_type = _resolve_reset_period(rule, form_data, field_defs)
    base = period_key_for(period_type, dt)
    scope_field = rule.get("period_scope_field") or (rule.get("reset_period_by_field") or {}).get("field_id")
    if scope_field:
        raw = (form_data or {}).get(str(scope_field))
        scope = str(raw) if raw not in (None, "") else (
            _field_value_text(str(scope_field), form_data, field_defs) or "_"
        )
        return f"{scope}:{base}" if base else scope
    return base

async def _build_serial_parts(
    db: AsyncSession | None, tenant_id: str | None, template_id: str | None,
    field_def: dict[str, Any], form_data: dict[str, Any], field_defs: list[dict[str, Any]],
    *, peek: bool,
) -> str:
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
            dt = _resolve_serial_dt(rule, form_data, now)
            pkey = _counter_period_key(rule, form_data, field_defs, dt)
            if peek:
                assert db is not None and tenant_id is not None and template_id is not None
                raw = await peek_counter_value(
                    db, tenant_id, template_id, str(field_def.get("id")), pkey, initial,
                )
            else:
                assert db is not None and tenant_id is not None and template_id is not None
                raw = await next_counter_value(
                    db, tenant_id, template_id, str(field_def.get("id")), pkey, initial,
                )
            num = raw % (10 ** digits)
            parts.append(str(num).zfill(digits) if rule.get("fixed", True) else str(num))
        elif rtype == "date":
            dt = _resolve_serial_dt(rule, form_data, now)
            fmt = _resolve_date_format(rule, form_data, field_defs)
            parts.append(format_serial_date(fmt, dt))
        elif rtype == "text":
            parts.append(str(rule.get("value") or ""))
        elif rtype == "field":
            parts.append(_field_value_text(str(rule.get("field_id") or ""), form_data, field_defs))
    return "".join(parts)


async def generate_serial_value(
    db: AsyncSession, tenant_id: str, template_id: str,
    field_def: dict[str, Any], form_data: dict[str, Any], field_defs: list[dict[str, Any]],
) -> str:
    """按 serial_rules 生成一条流水号(提交时调用)。"""
    return await _build_serial_parts(
        db, tenant_id, template_id, field_def, form_data, field_defs, peek=False,
    )


async def peek_serial_value(
    db: AsyncSession, tenant_id: str, template_id: str,
    field_def: dict[str, Any], form_data: dict[str, Any], field_defs: list[dict[str, Any]],
) -> str:
    """预览下一流水号（不消耗计数），供填报页「点击添加」即时展示。"""
    return await _build_serial_parts(
        db, tenant_id, template_id, field_def, form_data, field_defs, peek=True,
    )


async def generate_serials_for_submit(
    db: AsyncSession, tenant_id: str, template_id: str,
    field_defs: list[dict[str, Any]], form_data: dict[str, Any],
) -> dict[str, Any]:
    """提交链路入口: 为所有值为空的 auto_number 字段生成流水号(编辑/重提保留原值)。"""
    for fd in field_defs or []:
        if fd.get("type") == "auto_number" and not (form_data or {}).get(fd.get("id")):
            form_data[fd["id"]] = await generate_serial_value(db, tenant_id, template_id, fd, form_data, field_defs)
    return form_data


async def peek_serials_for_form(
    db: AsyncSession, tenant_id: str, template_id: str,
    field_defs: list[dict[str, Any]], form_data: dict[str, Any],
) -> dict[str, str]:
    """返回各 auto_number 字段的预览号。"""
    out: dict[str, str] = {}
    for fd in field_defs or []:
        fid = fd.get("id")
        if fd.get("type") == "auto_number" and fid:
            out[str(fid)] = await peek_serial_value(db, tenant_id, template_id, fd, form_data, field_defs)
    return out
