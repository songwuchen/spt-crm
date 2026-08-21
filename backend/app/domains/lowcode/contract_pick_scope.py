# -*- coding: utf-8 -*-
"""合同选择弹窗：部门过滤（支持多部门编制用户）。"""
from __future__ import annotations


def resolve_pick_department_ids(
    *,
    scope_all: bool,
    user_department_ids: list[str] | None,
    department_id: str | None = None,
    department_ids: list[str] | None = None,
    for_id_lookup: bool = False,
) -> list[str] | None:
    """解析合同选择弹窗的部门过滤。

    - scope_all：不过滤（返回 None）
    - for_id_lookup：按 id 回显时不做部门过滤
    - 用户挂在多个组织部门：并集过滤，不单看表单里一个「所在部门」
    - 单部门用户：优先表单 department_id，否则用户所在部门
    """
    if for_id_lookup or scope_all:
        return None

    user_depts = [x.strip() for x in (user_department_ids or []) if x and str(x).strip()]
    explicit = [x.strip() for x in (department_ids or []) if x and str(x).strip()]

    if explicit:
        if user_depts:
            allowed = set(user_depts)
            picked = [d for d in explicit if d in allowed]
            return picked or user_depts
        return explicit

    if len(user_depts) > 1:
        return user_depts

    form_dept = (department_id or "").strip()
    if form_dept:
        if user_depts and form_dept not in user_depts:
            return user_depts
        return [form_dept]

    return user_depts or None


def apply_contract_department_filter(conds, model, dept_ids: list[str] | None) -> None:
    """把部门条件追加到 SQLAlchemy where 列表。"""
    if not dept_ids:
        return
    if len(dept_ids) == 1:
        conds.append(model.department_id == dept_ids[0])
    else:
        conds.append(model.department_id.in_(dept_ids))
