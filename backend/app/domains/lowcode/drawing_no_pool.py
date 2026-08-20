# -*- coding: utf-8 -*-
"""图纸编号共用号池：合同登记 ↔ 合同图纸对应表。

两侧共用同一套 WMGF 流水计数，但落库表不同；预览/占号必须同时避开两边已占用号，
否则会出现「预览到对应表已用过的号 → 保存直接撞号」的时机差。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contract.models import Contract
from app.domains.lowcode.models import FormInstance


async def is_drawing_no_taken(
    db: AsyncSession,
    tenant_id: str,
    value: str,
    *,
    map_template_id: str,
    exclude_instance_id: str | None = None,
    exclude_contract_id: str | None = None,
) -> bool:
    """合同表或图纸对应表任一已占用即视为占用。"""
    v = (value or "").strip()
    if not v:
        return False
    cq = select(Contract.id).where(
        Contract.tenant_id == tenant_id,
        Contract.drawing_no == v,
    )
    if exclude_contract_id:
        cq = cq.where(Contract.id != exclude_contract_id)
    if (await db.execute(cq.limit(1))).scalar_one_or_none():
        return True
    fq = select(FormInstance.id).where(
        FormInstance.tenant_id == tenant_id,
        FormInstance.template_id == map_template_id,
        FormInstance.is_deleted == False,  # noqa: E712
        FormInstance.form_data["drawing_no"].astext == v,
    )
    if exclude_instance_id:
        fq = fq.where(FormInstance.id != exclude_instance_id)
    return (await db.execute(fq.limit(1))).scalar_one_or_none() is not None


async def peek_drawing_no_skipping_taken(
    db: AsyncSession,
    tenant_id: str,
    template_id: str,
    field_def: dict,
    form_data: dict,
    field_defs: list[dict],
    *,
    map_template_id: str | None = None,
    max_skip: int = 50,
) -> str:
    """预览下一可用图纸号：若计数落后于已占用号，推进计数跳过空洞，不白白展示撞号。"""
    from app.domains.lowcode.serial_number import generate_serial_value, peek_serial_value

    tpl = map_template_id or template_id
    last = ""
    for _ in range(max(1, max_skip)):
        last = await peek_serial_value(
            db, tenant_id, template_id, field_def, form_data, field_defs,
        )
        if not await is_drawing_no_taken(db, tenant_id, last, map_template_id=tpl):
            return last
        # 计数停在已占用号上：consume 掉该槽，再 peek 下一号
        await generate_serial_value(
            db, tenant_id, template_id, field_def, form_data, field_defs,
        )
    return last
