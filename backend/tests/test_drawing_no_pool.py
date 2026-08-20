# -*- coding: utf-8 -*-
"""图纸编号共用号池：合同登记 ↔ 合同图纸对应表。"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.domains.contract.models import Contract
from app.domains.lowcode.drawing_no_pool import (
    is_drawing_no_taken,
    peek_drawing_no_skipping_taken,
)
from app.domains.lowcode.models import FormInstance
from app.domains.lowcode.serial_number import peek_serial_value

TENANT = "00000000-0000-0000-0000-000000000001"
TPL = "00000000-0000-0000-0000-00000000cdmp"

DRAWING_FD = {
    "id": "drawing_no",
    "type": "auto_number",
    "label": "图纸编号",
    "props": {
        "serial_rules": [
            {"type": "text", "value": "T"},
            {"type": "counter", "digits": 3, "fixed": True, "initial_value": 1, "reset_period": "none"},
        ],
    },
}


@pytest.mark.asyncio
async def test_peek_skips_number_taken_by_contract(db: AsyncSession):
    """计数下一号若已被合同登记占用，预览应跳到空号。"""
    defs = [DRAWING_FD]
    peek1 = await peek_serial_value(db, TENANT, TPL, DRAWING_FD, {}, defs)
    assert peek1 == "T001"

    db.add(Contract(
        id=generate_uuid(),
        tenant_id=TENANT,
        contract_no=f"C-{generate_uuid()[:8]}",
        drawing_no="T001",
        current_version_no=1,
    ))
    await db.flush()

    assert await is_drawing_no_taken(db, TENANT, "T001", map_template_id=TPL)

    nxt = await peek_drawing_no_skipping_taken(
        db, TENANT, TPL, DRAWING_FD, {}, defs, map_template_id=TPL,
    )
    assert nxt == "T002"
    # 再 peek 仍是 T002（未正式 consume 预览号）
    nxt2 = await peek_drawing_no_skipping_taken(
        db, TENANT, TPL, DRAWING_FD, {}, defs, map_template_id=TPL,
    )
    assert nxt2 == "T002"


@pytest.mark.asyncio
async def test_peek_skips_number_taken_by_form_instance(db: AsyncSession):
    defs = [DRAWING_FD]
    db.add(FormInstance(
        id=generate_uuid(),
        tenant_id=TENANT,
        template_id=TPL,
        template_version_id=generate_uuid(),
        status="draft",
        initiator_id="00000000-0000-0000-0000-000000000099",
        form_data={"drawing_no": "T001"},
        field_definitions=defs,
    ))
    await db.flush()

    nxt = await peek_drawing_no_skipping_taken(
        db, TENANT, TPL, DRAWING_FD, {}, defs, map_template_id=TPL,
    )
    assert nxt == "T002"
