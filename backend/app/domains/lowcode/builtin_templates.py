"""内置表单模板库（模板市场 MVP）。

提供一批开箱即用的常见企业表单，管理员可一键安装为本租户的草稿表单，
再按需在设计器里增删字段/绑定审批流后发布。字段结构与 FormRenderer/表单引擎一致
（id 为稳定 slug，type 取自 FieldType，options 为 [{label,value}]）。
"""
from __future__ import annotations

from typing import Any


def _opt(*labels: str) -> list[dict[str, str]]:
    return [{"label": s, "value": s} for s in labels]


BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "key": "leave_request",
        "name": "请假申请",
        "category": "人事行政",
        "icon": "CalendarOutlined",
        "description": "员工请假申请，含请假类型、起止时间与事由，可绑定审批流。",
        "field_definitions": [
            {"id": "leave_type", "type": "select", "label": "请假类型", "required": True,
             "options": _opt("事假", "病假", "年假", "调休", "婚假", "产假", "陪产假", "丧假")},
            {"id": "start_at", "type": "datetime", "label": "开始时间", "required": True},
            {"id": "end_at", "type": "datetime", "label": "结束时间", "required": True},
            {"id": "days", "type": "number", "label": "请假天数", "required": True},
            {"id": "reason", "type": "textarea", "label": "请假事由", "required": True},
            {"id": "handover", "type": "text", "label": "工作交接人"},
        ],
    },
    {
        "key": "expense_reimbursement",
        "name": "报销申请",
        "category": "财务",
        "icon": "AccountBookOutlined",
        "description": "费用报销申请，含报销明细子表与金额合计，可绑定审批流。",
        "field_definitions": [
            {"id": "expense_type", "type": "select", "label": "报销类型", "required": True,
             "options": _opt("差旅费", "招待费", "办公费", "交通费", "通讯费", "其他")},
            {"id": "happen_date", "type": "date", "label": "费用发生日期", "required": True},
            {"id": "detail", "type": "detail_table", "label": "报销明细", "required": True,
             "detail_table_columns": [
                 {"id": "item", "type": "text", "label": "费用项目", "required": True},
                 {"id": "amount", "type": "amount", "label": "金额", "required": True},
                 {"id": "note", "type": "text", "label": "备注"},
             ]},
            {"id": "total_amount", "type": "amount", "label": "报销总额", "required": True},
            {"id": "attachments", "type": "file", "label": "发票/附件"},
            {"id": "remark", "type": "textarea", "label": "说明"},
        ],
    },
    {
        "key": "seal_use",
        "name": "用章申请",
        "category": "人事行政",
        "icon": "SafetyCertificateOutlined",
        "description": "公章/合同章使用申请，含用章类型、文件与事由，可绑定审批流。",
        "field_definitions": [
            {"id": "seal_type", "type": "select", "label": "用章类型", "required": True,
             "options": _opt("公章", "合同章", "财务章", "法人章", "发票专用章")},
            {"id": "doc_name", "type": "text", "label": "文件名称", "required": True},
            {"id": "use_date", "type": "date", "label": "用章日期", "required": True},
            {"id": "copies", "type": "number", "label": "份数"},
            {"id": "reason", "type": "textarea", "label": "用章事由", "required": True},
            {"id": "attachments", "type": "file", "label": "相关附件"},
        ],
    },
    {
        "key": "item_requisition",
        "name": "物品领用",
        "category": "人事行政",
        "icon": "InboxOutlined",
        "description": "办公物品/耗材领用申请，含物品明细子表。",
        "field_definitions": [
            {"id": "use_date", "type": "date", "label": "领用日期", "required": True},
            {"id": "items", "type": "detail_table", "label": "领用明细", "required": True,
             "detail_table_columns": [
                 {"id": "name", "type": "text", "label": "物品名称", "required": True},
                 {"id": "qty", "type": "number", "label": "数量", "required": True},
                 {"id": "unit", "type": "text", "label": "单位"},
             ]},
            {"id": "purpose", "type": "textarea", "label": "用途说明"},
        ],
    },
    {
        "key": "purchase_request",
        "name": "采购申请",
        "category": "采购",
        "icon": "ShoppingCartOutlined",
        "description": "采购需求申请，含采购明细、预算金额与期望到货日，可绑定审批流。",
        "field_definitions": [
            {"id": "dept", "type": "text", "label": "申请部门", "required": True},
            {"id": "expect_date", "type": "date", "label": "期望到货日期"},
            {"id": "items", "type": "detail_table", "label": "采购明细", "required": True,
             "detail_table_columns": [
                 {"id": "name", "type": "text", "label": "物料名称", "required": True},
                 {"id": "spec", "type": "text", "label": "规格型号"},
                 {"id": "qty", "type": "number", "label": "数量", "required": True},
                 {"id": "price", "type": "amount", "label": "预估单价"},
             ]},
            {"id": "budget", "type": "amount", "label": "预算金额", "required": True},
            {"id": "reason", "type": "textarea", "label": "采购事由", "required": True},
        ],
    },
]


def list_builtin() -> list[dict[str, Any]]:
    """列表展示用（不含完整字段定义，减小体积）。"""
    return [
        {
            "key": t["key"], "name": t["name"], "category": t.get("category"),
            "icon": t.get("icon"), "description": t.get("description"),
            "field_count": len(t["field_definitions"]),
        }
        for t in BUILTIN_TEMPLATES
    ]


def get_builtin(key: str) -> dict[str, Any] | None:
    return next((t for t in BUILTIN_TEMPLATES if t["key"] == key), None)
