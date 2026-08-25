"""合同登记流水号 — 对齐简道云 sn 规则：1.2.3-{yyyyMMdd}{5位年序号}."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# lc_serial_counter 作用域（非低代码表单实例，固定占位 template/field）
CONTRACT_SERIAL_COUNTER_TEMPLATE_ID = "00000000-0000-4000-a001-000000000001"
CONTRACT_SERIAL_FIELD_ID = "serial_no"

CONTRACT_SERIAL_RULES: list[dict[str, Any]] = [
    {"type": "text", "value": "1.2.3-"},
    {"type": "date", "format": "yyyyMMdd"},
    {
        "type": "counter",
        "digits": 5,
        "fixed": True,
        "reset_period": "yearly",
        "initial_value": 1,
    },
]

CONTRACT_SERIAL_FIELD_DEF: dict[str, Any] = {
    "id": CONTRACT_SERIAL_FIELD_ID,
    "type": "auto_number",
    "label": "流水号",
    "available_on_create": True,
    "fill_stage": "initiator",
    "form_editable": False,
    "props": {"serial_rules": CONTRACT_SERIAL_RULES},
}


def _form_data_for_serial(*, ref_date: date | datetime | None = None) -> dict[str, Any]:
    if ref_date is None:
        return {}
    if isinstance(ref_date, datetime):
        d = ref_date.date()
    else:
        d = ref_date
    return {"card_date": d.isoformat()}


async def peek_contract_serial_no(
    db: AsyncSession,
    tenant_id: str,
    *,
    ref_date: date | datetime | None = None,
) -> str:
    from app.domains.lowcode.serial_number import peek_serial_value

    return await peek_serial_value(
        db,
        tenant_id,
        CONTRACT_SERIAL_COUNTER_TEMPLATE_ID,
        CONTRACT_SERIAL_FIELD_DEF,
        _form_data_for_serial(ref_date=ref_date),
        [CONTRACT_SERIAL_FIELD_DEF],
    )


async def allocate_contract_serial_no(
    db: AsyncSession,
    tenant_id: str,
    *,
    ref_date: date | datetime | None = None,
    preset: str | None = None,
) -> str:
    """新建合同登记取号；openapi 传入 preset 时原样保留（非空）。"""
    if preset and str(preset).strip():
        return str(preset).strip()
    from app.domains.lowcode.serial_number import generate_serial_value

    return await generate_serial_value(
        db,
        tenant_id,
        CONTRACT_SERIAL_COUNTER_TEMPLATE_ID,
        CONTRACT_SERIAL_FIELD_DEF,
        _form_data_for_serial(ref_date=ref_date),
        [CONTRACT_SERIAL_FIELD_DEF],
    )
