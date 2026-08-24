# -*- coding: utf-8 -*-
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.dept_equivalence import (
    METALLURGY_MINING_SALES_EQUIVALENT_NAMES,
    dept_name_in_metallurgy_equivalence,
    expand_equivalent_department_ids,
    expand_equivalent_department_names,
)


def test_dept_name_in_metallurgy_equivalence():
    assert dept_name_in_metallurgy_equivalence("冶金矿山装备销售事业部")
    assert dept_name_in_metallurgy_equivalence("（暂存）冶金装备销售事业部")
    assert not dept_name_in_metallurgy_equivalence("市场支持中心")


def test_expand_equivalent_department_names():
    out = expand_equivalent_department_names(["冶金矿山装备销售事业部"])
    assert out is not None
    assert METALLURGY_MINING_SALES_EQUIVALENT_NAMES.issubset(set(out))
    assert expand_equivalent_department_names(["市场支持中心"]) == ["市场支持中心"]


@pytest.mark.asyncio
async def test_expand_equivalent_department_ids():
    db = MagicMock()
    mine_id = "cdd42ec3-a6a6-4219-a5e1-39eacf0b1178"
    staging_id = "1401e71f-d421-4abd-bad2-7e133f35584c"
    calls = {"n": 0}

    async def fake_execute(_stmt):
        calls["n"] += 1
        result = MagicMock()
        if calls["n"] == 1:
            result.all.return_value = [(mine_id, "冶金矿山装备销售事业部")]
        else:
            result.scalars.return_value.all.return_value = [staging_id, mine_id]
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    expanded = await expand_equivalent_department_ids(db, "t1", [mine_id])
    assert set(expanded) == {mine_id, staging_id}


@pytest.mark.asyncio
async def test_expand_equivalent_department_ids_skips_unrelated():
    db = MagicMock()
    other_id = "other-dept"

    async def fake_execute(stmt):
        result = MagicMock()
        result.all.return_value = [(other_id, "市场支持中心")]
        return result

    db.execute = AsyncMock(side_effect=fake_execute)
    expanded = await expand_equivalent_department_ids(db, "t1", [other_id])
    assert expanded == [other_id]
