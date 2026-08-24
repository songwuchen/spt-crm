# -*- coding: utf-8 -*-
"""组织部门等价：简道云迁移后「暂存」部门与正式事业部数据互通。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.organization.models import Department

# 冶金矿山 ↔ 简道云暂存冶金：同一业务线，选合同/看列表时并集可见
METALLURGY_MINING_SALES_EQUIVALENT_NAMES: frozenset[str] = frozenset({
    "冶金矿山装备销售事业部",
    "（暂存）冶金装备销售事业部",
    "(暂存)冶金装备销售事业部",
    "(暂存）冶金装备销售事业部",
})


def dept_name_in_metallurgy_equivalence(name: str | None) -> bool:
    return (name or "").strip() in METALLURGY_MINING_SALES_EQUIVALENT_NAMES


async def expand_equivalent_department_ids(
    db: AsyncSession,
    tenant_id: str,
    dept_ids: list[str] | None,
) -> list[str] | None:
    """若用户/筛选部门命中冶金等价组，则并上组内全部部门 id。"""
    if not dept_ids:
        return dept_ids
    uniq = list(dict.fromkeys(str(d).strip() for d in dept_ids if d and str(d).strip()))
    if not uniq:
        return dept_ids

    rows = (await db.execute(
        select(Department.id, Department.name).where(
            Department.tenant_id == tenant_id,
            Department.id.in_(uniq),
        )
    )).all()
    if not any(dept_name_in_metallurgy_equivalence(name) for _, name in rows):
        return uniq

    eq_ids = list((await db.execute(
        select(Department.id).where(
            Department.tenant_id == tenant_id,
            Department.name.in_(list(METALLURGY_MINING_SALES_EQUIVALENT_NAMES)),
        )
    )).scalars().all())
    expanded = {*uniq, *(str(x) for x in eq_ids if x)}
    return list(expanded)


def expand_equivalent_department_names(names: list[str] | None) -> list[str] | None:
    """文本部门字段匹配：命中等价组则并上组内全部名称。"""
    if not names:
        return names
    literals = [str(n).strip() for n in names if n and str(n).strip()]
    if not literals:
        return names
    if not any(dept_name_in_metallurgy_equivalence(n) for n in literals):
        return literals
    return list({*literals, *METALLURGY_MINING_SALES_EQUIVALENT_NAMES})
