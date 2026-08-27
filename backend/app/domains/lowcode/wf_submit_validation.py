"""审批节点提交校验（对齐简道云节点 validator / 表单提交校验）。

节点定义可挂 submit_validations: [{formula, message}]；
公式为真才允许通过，否则拦截并返回 message。
"""
from __future__ import annotations

from typing import Any

from app.common.error_codes import VALIDATION_ERROR
from app.common.exceptions import BusinessException


def parse_submit_validations(node: dict | None) -> list[dict[str, str]]:
    """规范化节点 submit_validations → [{formula, message}]。"""
    out: list[dict[str, str]] = []
    for raw in (node or {}).get("submit_validations") or []:
        if not isinstance(raw, dict):
            continue
        formula = str(raw.get("formula") or "").strip()
        if not formula:
            continue
        message = str(raw.get("message") or raw.get("remind") or "").strip()
        out.append({"formula": formula, "message": message})
    return out


def assert_node_submit_validations(
    node: dict | None,
    *,
    form_data: dict[str, Any],
    field_updates: dict[str, Any] | None,
    form_fields: list[dict[str, Any]] | None,
    action: str,
    current_user_name: str = "",
    extras: dict[str, Any] | None = None,
) -> None:
    """approve 时按节点 submit_validations 校验；不通过则抛 VALIDATION_ERROR。"""
    if action != "approve":
        return
    rules = parse_submit_validations(node)
    if not rules:
        return
    from app.domains.lowcode.formula_engine import (
        compute_formula_fields,
        evaluate_submit_validations,
    )

    merged = {**(form_data or {}), **(field_updates or {})}
    merged = compute_formula_fields(
        merged,
        list(form_fields or []),
        current_user_name=current_user_name,
        extras=extras,
    )
    msg = evaluate_submit_validations(
        merged,
        list(form_fields or []),
        rules,
        current_user_name=current_user_name,
        extras=extras,
    )
    if msg:
        raise BusinessException(code=VALIDATION_ERROR, message=msg)
