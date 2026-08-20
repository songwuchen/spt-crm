# -*- coding: utf-8 -*-
"""可手改流水号：提交预览号时必须占计数，避免撞号。"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.lowcode.serial_number import (
    generate_serials_for_submit,
    peek_serial_value,
)

TENANT = "00000000-0000-0000-0000-000000000001"

DRAWING_FD = {
    "id": "drawing_no",
    "type": "auto_number",
    "label": "图纸编号",
    "form_editable": True,
    "props": {
        "manual_edit": True,
        "serial_rules": [
            {"type": "text", "value": "T"},
            {"type": "counter", "digits": 3, "fixed": True, "initial_value": 1, "reset_period": "none"},
        ],
    },
}


@pytest.mark.asyncio
async def test_manual_edit_peek_value_consumes_counter(db: AsyncSession):
    """前端把 peek 写入 form_data 后再保存，须推进计数，第二单不得同号。"""
    tpl_id = "00000000-0000-0000-0000-00000000cd01"
    defs = [DRAWING_FD]

    peek1 = await peek_serial_value(db, TENANT, tpl_id, DRAWING_FD, {}, defs)
    assert peek1 == "T001"

    fd1 = {"drawing_no": peek1}
    out1 = await generate_serials_for_submit(db, TENANT, tpl_id, defs, fd1)
    assert out1["drawing_no"] == "T001"

    peek2 = await peek_serial_value(db, TENANT, tpl_id, DRAWING_FD, {}, defs)
    assert peek2 == "T002"

    fd2 = {"drawing_no": peek2}
    out2 = await generate_serials_for_submit(db, TENANT, tpl_id, defs, fd2)
    assert out2["drawing_no"] == "T002"
    assert out1["drawing_no"] != out2["drawing_no"]


@pytest.mark.asyncio
async def test_manual_custom_value_kept(db: AsyncSession):
    tpl_id = "00000000-0000-0000-0000-00000000cd02"
    defs = [DRAWING_FD]
    fd = {"drawing_no": "CUSTOM-9"}
    out = await generate_serials_for_submit(db, TENANT, tpl_id, defs, fd)
    assert out["drawing_no"] == "CUSTOM-9"


@pytest.mark.asyncio
async def test_allocate_unique_skips_taken(db: AsyncSession):
    from app.domains.lowcode.serial_number import allocate_unique_serials

    tpl_id = "00000000-0000-0000-0000-00000000cd03"
    defs = [DRAWING_FD]
    taken = {"T001"}

    async def is_taken(_fid: str, value: str) -> bool:
        return value in taken

    out = await allocate_unique_serials(
        db, TENANT, tpl_id, defs, {},
        field_ids=["drawing_no"],
        is_taken=is_taken,
    )
    assert out["drawing_no"] == "T002"


@pytest.mark.asyncio
async def test_allocate_keeps_available_current(db: AsyncSession):
    """当前号未占用时不推进计数，连点重新取号不得空耗号段。"""
    from app.domains.lowcode.serial_number import allocate_unique_serials

    tpl_id = "00000000-0000-0000-0000-00000000cd04"
    defs = [DRAWING_FD]
    taken: set[str] = set()

    async def is_taken(_fid: str, value: str) -> bool:
        return value in taken

    first = await allocate_unique_serials(
        db, TENANT, tpl_id, defs, {},
        field_ids=["drawing_no"],
        is_taken=is_taken,
    )
    assert first["drawing_no"] == "T001"

    again = await allocate_unique_serials(
        db, TENANT, tpl_id, defs, {"drawing_no": "T001"},
        field_ids=["drawing_no"],
        is_taken=is_taken,
    )
    assert again["drawing_no"] == "T001"
    peek = await peek_serial_value(db, TENANT, tpl_id, DRAWING_FD, {}, defs)
    assert peek == "T002"  # 计数仍停在下一号，未因连点前进


@pytest.mark.asyncio
async def test_allocate_replaces_when_current_taken(db: AsyncSession):
    from app.domains.lowcode.serial_number import allocate_unique_serials

    tpl_id = "00000000-0000-0000-0000-00000000cd05"
    defs = [DRAWING_FD]
    taken = {"T001"}

    async def is_taken(_fid: str, value: str) -> bool:
        return value in taken

    out = await allocate_unique_serials(
        db, TENANT, tpl_id, defs, {"drawing_no": "T001"},
        field_ids=["drawing_no"],
        is_taken=is_taken,
    )
    assert out["drawing_no"] == "T002"
