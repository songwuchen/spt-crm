"""合同图纸领用字段后处理：流水号 / 默认值 / 去掉文本桩。"""
from __future__ import annotations

from typing import Any

# 简道云 sn：createTime yyyyMMdd + 2 位日重置 → 2026081301
DRAWING_REQUISITION_SERIAL_RULES: list[dict[str, Any]] = [
    {"type": "date", "format": "yyyyMMdd"},
    {
        "type": "counter",
        "digits": 2,
        "fixed": True,
        "reset_period": "daily",
        "initial_value": 1,
    },
]

_DROP_IDS = frozenset({"order_person_text", "designer_text", "need_decrypt_note"})


def apply_drawing_requisition_fields(field_defs: list[dict[str, Any]]) -> None:
    """就地修正 drawing_requisition 字段定义。"""
    from app.domains.lowcode.pickable_scope import apply_scheme_design_person_scope_rules

    defs = field_defs if isinstance(field_defs, list) else []
    keep: list[dict[str, Any]] = []
    for f in defs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid in _DROP_IDS:
            continue
        if fid == "applicant":
            props = dict(f.get("props") or {})
            props["default_current_user"] = True
            f["props"] = props
        elif fid == "department":
            props = dict(f.get("props") or {})
            props["default_current_dept"] = True
            f["props"] = props
        elif fid == "apply_datetime":
            f["type"] = "date"
            props = dict(f.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            props["default_today"] = True
            f["props"] = props
        elif fid == "order_date":
            f["type"] = "date"
            props = dict(f.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            props.pop("default_today", None)
            props["default_today_on_approve"] = True
            f["props"] = props
        elif fid == "contract_no":
            f["type"] = "contract"
            f["label"] = "合同号"
            f["description"] = "从合同管理中选择；按图纸编号搜索，选项以图纸编号显示。"
            f.pop("options", None)
        keep.append(f)

    serial = next((f for f in keep if f.get("id") == "serial_no"), None)
    if serial is None:
        serial = {
            "id": "serial_no",
            "type": "auto_number",
            "label": "流水号",
            "available_on_create": True,
            "fill_stage": "initiator",
            "form_editable": False,
            "description": "对齐简道云：yyyyMMdd + 两位日序，如 2026081301。",
        }
        keep.insert(0, serial)
    serial["type"] = "auto_number"
    serial["label"] = "流水号"
    serial["form_editable"] = False
    serial["available_on_create"] = True
    serial["fill_stage"] = "initiator"
    props = dict(serial.get("props") or {}) if isinstance(serial.get("props"), dict) else {}
    props["serial_rules"] = [dict(r) for r in DRAWING_REQUISITION_SERIAL_RULES]
    serial["props"] = props

    defs[:] = keep
    apply_scheme_design_person_scope_rules(defs)
