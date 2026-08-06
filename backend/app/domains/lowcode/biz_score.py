# -*- coding: utf-8 -*-
"""方案/安装图「业务打分」字段：创建页隐藏，审批节点填写。

简道云：态度 0–20、进度准确性 0–40、专业技能 0–40；总分 = 三者之和。
"""
from __future__ import annotations

from typing import Any

SCORE_REQUIRED_FIELDS = ("score_attitude", "score_progress", "score_skill")
SCORE_OPTIONAL_FIELDS = ("score_date",)
SCORE_TOTAL_FIELD = "score_total"

_SCORE_LIMITS: dict[str, dict[str, Any]] = {
    "score_attitude": {"min": 0, "max": 20, "precision": 1},
    "score_progress": {"min": 0, "max": 40, "precision": 1},
    "score_skill": {"min": 0, "max": 40, "precision": 1},
}

BIZ_SCORE_NODE_NAMES = frozenset({"业务打分", "业务反馈"})

BIZ_SCORE_FIELD_PERMS: list[dict[str, str]] = [
    {"field": "score_attitude", "access": "required"},
    {"field": "score_progress", "access": "required"},
    {"field": "score_skill", "access": "required"},
    {"field": "score_date", "access": "editable"},
]


def apply_biz_score_field_defs(field_defs: list[dict[str, Any]]) -> None:
    """创建隐藏打分项；总分改为公式求和。"""
    for fd in field_defs or []:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        if fid in _SCORE_LIMITS:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False  # 必填下沉到节点 field_perms
            props = dict(fd.get("props") or {}) if isinstance(fd.get("props"), dict) else {}
            props.update(_SCORE_LIMITS[fid])
            fd["props"] = props
        elif fid == SCORE_TOTAL_FIELD:
            fd["type"] = "formula"
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
            fd["props"] = {
                "formula": "SUM($score_attitude#,$score_progress#,$score_skill#)",
            }
        elif fid == "score_date":
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
            props = dict(fd.get("props") or {}) if isinstance(fd.get("props"), dict) else {}
            props["default_today"] = True
            fd["props"] = props


def _merge_score_perms(existing: list | None) -> list[dict[str, str]]:
    by_field: dict[str, str] = {}
    for p in existing or []:
        if not isinstance(p, dict) or not p.get("field"):
            continue
        acc = p.get("access") or "editable"
        if acc not in ("editable", "required"):
            acc = "editable"
        by_field[str(p["field"])] = acc
    for p in BIZ_SCORE_FIELD_PERMS:
        fid = p["field"]
        # 已有 required 保留；否则用打分规则
        if fid not in by_field or by_field[fid] != "required":
            by_field[fid] = p["access"]
    return [{"field": k, "access": v} for k, v in by_field.items()]


def apply_biz_score_flow_nodes(nodes: list[dict[str, Any]] | None) -> None:
    """给「业务打分」「业务反馈」节点挂上三项分数（+打分日期）可填权限。"""
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") not in BIZ_SCORE_NODE_NAMES:
            continue
        n["field_perms"] = _merge_score_perms(n.get("field_perms"))


def flow_missing_biz_score_perms(nodes: list | None) -> bool:
    """「业务打分」或「业务反馈」节点缺少三项分数权限 → 需要升级。"""
    saw_target = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") not in BIZ_SCORE_NODE_NAMES:
            continue
        saw_target = True
        fps = {
            p.get("field")
            for p in (n.get("field_perms") or [])
            if isinstance(p, dict)
        }
        if not set(SCORE_REQUIRED_FIELDS) <= fps:
            return True
    # 方案流应有「业务打分」；若节点都没有则不算 missing（避免误伤无关流）
    return False if saw_target else False
