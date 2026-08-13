# -*- coding: utf-8 -*-
"""安装图设计通知：创建/审批阶段与只读回填（对齐简道云发起节点 optAuth）。"""
from __future__ import annotations

from typing import Any

# 发起仅可见（联动/系统回填），创建页展示但不可手改
_START_READONLY = frozenset({
    "serial_no", "sales_person", "customer_name", "matter", "applicant", "design_card_no",
})

# 无发起 optAuth、仅审批节点使用
_APPROVER_ONLY = frozenset({
    "biz_feedback", "lose_bid_reason",
    "design_dispatch", "transfer_packaging_users", "design_assignees",
    "offices_multi", "order_date", "transfer_sw_lwt",
    "need_submit_drawing",
    "score_attitude", "score_progress", "score_skill",
    "score_total", "score_date", "remark",
})

# 伴随文本：创建区展示
_INITIATOR_COMPANIONS = frozenset({
    "dept_code", "pre_designer_text",
})

_DROP_IDS = frozenset({"order_person_text"})


def apply_install_drawing_notice_fields(field_defs: list[dict[str, Any]]) -> None:
    """对齐简道云：创建可写 / 发起只读 / 审批才填；并补默认值。"""
    from app.domains.lowcode.biz_score import apply_biz_score_field_defs

    if isinstance(field_defs, list):
        field_defs[:] = [
            fd for fd in field_defs
            if not (isinstance(fd, dict) and fd.get("id") in _DROP_IDS)
        ]

    apply_biz_score_field_defs(field_defs)
    for fd in field_defs or []:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        if not fid:
            continue
        if fid in _START_READONLY:
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            fd["form_editable"] = False
            if fd.get("required"):
                fd["required"] = False
        elif fid in _APPROVER_ONLY:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            if fd.get("required"):
                fd["required"] = False
        elif fid in _INITIATOR_COMPANIONS:
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
        elif fid == "change_scheme":
            # 简道云发起节点 optAuth 未挂该子表，创建不可见；详情只读仍可看历史
            fd["available_on_create"] = False
            fd["required"] = False
            fd.pop("fill_stage", None)

        if fid == "project_no":
            # 简道云 combo 拉外部「项目号」表 → CRM 改为选商机管理编号
            fd["type"] = "project"
            fd["label"] = fd.get("label") or "项目号选择"
            fd["required"] = True
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            fd["description"] = "从商机管理选择项目编号；选中后带出业务员/公司名称/事项。"
            props = dict(fd.get("props") or {})
            props["prefer_code"] = True
            props["project_fill"] = "install_notice"
            fd["props"] = props
            fd.pop("options", None)
        elif fid == "applicant":
            props = dict(fd.get("props") or {})
            props["default_current_user"] = True
            fd["props"] = props
        elif fid == "department":
            props = dict(fd.get("props") or {})
            props["default_current_dept"] = True
            fd["props"] = props
        elif fid in ("apply_datetime", "card_date", "require_draw_date", "order_date"):
            # 简道云虽标 datetime，format 为 yyyy-MM-dd → 只选日期
            fd["type"] = "date"
            props = dict(fd.get("props") or {})
            props["show_time"] = False
            props["date_only"] = True
            if fid in ("apply_datetime", "card_date", "order_date"):
                props["default_today"] = True
            fd["props"] = props
        elif fid == "offices_multi":
            fd["type"] = "department_multi"
            fd["label"] = fd.get("label") or "科室"
        elif fid == "transfer_packaging_users":
            fd["type"] = "person_multi"
        elif fid == "design_assignees":
            fd["type"] = "person_multi"
        elif fid in ("scheme_detail", "install_env", "scheme_material"):
            props = dict(fd.get("props") or {})
            props["ensure_min_rows"] = 1
            fd["props"] = props
        elif fid == "remark":
            # 打分备注：创建隐藏，业务反馈节点填写
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
