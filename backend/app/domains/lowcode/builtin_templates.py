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
    {
        "key": "drawing_requisition",
        "name": "合同图纸（资料）领用申请",
        "category": "图纸",
        "icon": "FileImageOutlined",
        "description": "对齐简道云通用流程「合同图纸（资料）领用申请」。字段见 docs/product/_jdy_drawing_forms.md。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "install_drawing_notice",
        "name": "安装图设计通知",
        "category": "图纸",
        "icon": "BuildOutlined",
        "description": "对齐简道云通用流程「安装图设计通知」。字段见 docs/product/_jdy_drawing_forms.md。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "scheme_management",
        "name": "方案管理",
        "category": "图纸",
        "icon": "BulbOutlined",
        "description": (
            "独立合成表单：有合同号→领用字段/审批；无合同号→安装图/投标方案字段/审批。"
            "不与 drawing_requisition / install_drawing_notice 共用 code。"
        ),
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "prod_card_supplement",
        "name": "生产卡/补充流程",
        "category": "合同",
        "icon": "ContainerOutlined",
        "description": "对齐简道云数据中心「生产卡/补充流程」。字段见 docs/product/_jdy_prod_card_forms.md。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "invoice_application",
        "name": "开票申请",
        "category": "合同",
        "icon": "FileTextOutlined",
        "description": "对齐简道云数据中心「开票申请」。字段见 docs/product/_jdy_invoice_application_forms.md。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "payment_registration",
        "name": "收款登记",
        "category": "合同",
        "icon": "AccountBookOutlined",
        "description": "对齐简道云数据中心「收款登记」。字段见 docs/product/_jdy_payment_registration_forms.md。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "quote_management",
        "name": "报价管理",
        "category": "合同",
        "icon": "AuditOutlined",
        "description": (
            "对齐简道云通用流程「核价管理流程」(app=5e6c73fe… entry=5e6c740e…)。"
            "产品名报价管理；流水号 HJ+yyyyMMdd+三位日序。"
            "详见 docs/product/_jdy_quote_management_forms.md。"
        ),
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "contract_drawing_map",
        "name": "合同图纸对应表",
        "category": "图纸",
        "icon": "ApartmentOutlined",
        "description": (
            "简道云「图纸档案管理」→「合同图纸对应表」(app=5b2af2c3… entry=5b2af2e1…)。"
            "编号规则：WMGF+yyyyMM+三位月序（如 WMGF202608018）；SY+yy+三位年序。"
            "合同登记创建时按此规则自动生成图纸编号（不再从本表选数回填）。"
        ),
        "sync_fields": True,
        "field_definitions": [
            {"id": "pre_issue", "type": "radio", "label": "预下号", "required": True,
             "options": _opt("是", "否"), "default_value": "否"},
            {"id": "apply_date", "type": "date", "label": "日期时间", "required": True,
             "props": {"default_today": True}},
            {"id": "number_attr", "type": "radio", "label": "编号属性", "required": True,
             "options": _opt("WMGF", "SY"), "default_value": "WMGF"},
            {"id": "contract_no", "type": "text", "label": "合同号", "required": True},
            {"id": "department", "type": "department", "label": "业务部门"},
            {
                "id": "drawing_no", "type": "auto_number", "label": "图纸编号",
                "props": {
                    "serial_rules": [
                        {"type": "field", "field_id": "number_attr"},
                        {
                            "type": "date",
                            "date_field": "apply_date",
                            "format": "yyyyMM",
                            "format_by_field": {
                                "field_id": "number_attr",
                                "map": {"WMGF": "yyyyMM", "SY": "yy"},
                            },
                        },
                        {
                            "type": "counter",
                            "digits": 3,
                            "fixed": True,
                            "initial_value": 1,
                            "date_field": "apply_date",
                            "reset_period": "monthly",
                            "reset_period_by_field": {
                                "field_id": "number_attr",
                                "map": {"WMGF": "monthly", "SY": "yearly"},
                            },
                            "period_scope_field": "number_attr",
                        },
                    ],
                },
            },
            {"id": "remark", "type": "textarea", "label": "备注"},
        ],
    },
    {
        "key": "application_field",
        "name": "应用领域",
        "category": "合同",
        "icon": "AppstoreOutlined",
        "description": (
            "简道云数据中心「应用领域（基础表）」"
            "(app=56ca77ce… entry=61cc1607…)。"
            "合同登记「应用领域」下拉从此表取选项。"
        ),
        "sync_fields": True,
        "field_definitions": [
            {"id": "name", "type": "text", "label": "应用领域", "required": True},
            {"id": "remark", "type": "textarea", "label": "备注"},
        ],
    },
    {
        "key": "application_material",
        "name": "应用物料",
        "category": "合同",
        "icon": "InboxOutlined",
        "description": (
            "简道云数据中心「物料表（基础表）」"
            "(app=56ca77ce… entry=5f1fdad6…)。"
            "合同登记「应用物料」下拉从此表取选项。"
        ),
        "sync_fields": True,
        "field_definitions": [
            {"id": "name", "type": "text", "label": "物料名称", "required": True},
            {"id": "remark", "type": "textarea", "label": "备注"},
        ],
    },
    {
        "key": "material_name",
        "name": "物料名称",
        "category": "合同",
        "icon": "TagsOutlined",
        "description": (
            "简道云通用流程「物料名称」"
            "(app=5e6c73fe… entry=6470532c…)。"
            "图纸/方案等物料选项源；与「应用物料」不是同一张表。"
            "详见 docs/product/_jdy_material_name_forms.md。"
        ),
        "sync_fields": True,
        "field_definitions": [
            {"id": "name", "type": "text", "label": "物料名称", "required": True},
            {"id": "remark", "type": "textarea", "label": "备注"},
        ],
    },
    {
        "key": "department_code_base",
        "name": "部门编号基础表",
        "category": "图纸",
        "icon": "ApartmentOutlined",
        "description": (
            "简道云通用流程「部门编号基础表」(entry=652a5357…)。"
            "方案管理/安装图选部门后自动回填「部门编号」；新设计卡号按「部门编号-yyyyMMdd+两位日序」生成。"
        ),
        "sync_fields": True,
        "field_definitions": [
            {"id": "department", "type": "department", "label": "部门", "required": True},
            {"id": "dept_code", "type": "text", "label": "编号", "required": True},
        ],
    },
]


def _apply_drawing_jdy_fields() -> None:
    try:
        from app.domains.lowcode._drawing_jdy_generated import DRAWING_JDY
    except Exception:
        DRAWING_JDY = {}
    try:
        from app.domains.lowcode._scheme_management_generated import SCHEME_MANAGEMENT_JDY
    except Exception:
        SCHEME_MANAGEMENT_JDY = {}
    try:
        from app.domains.lowcode._prod_card_jdy_generated import PROD_CARD_JDY
    except Exception:
        PROD_CARD_JDY = {}
    try:
        from app.domains.lowcode._invoice_payment_jdy_generated import INVOICE_PAYMENT_JDY
    except Exception:
        INVOICE_PAYMENT_JDY = {}
    try:
        from app.domains.lowcode._quote_management_generated import QUOTE_MANAGEMENT_JDY
    except Exception:
        QUOTE_MANAGEMENT_JDY = {}
    packs = {
        **DRAWING_JDY, **SCHEME_MANAGEMENT_JDY, **PROD_CARD_JDY,
        **INVOICE_PAYMENT_JDY, **QUOTE_MANAGEMENT_JDY,
    }
    for t in BUILTIN_TEMPLATES:
        pack = packs.get(t["key"])
        if not pack:
            continue
        defs = []
        for fd in pack.get("field_definitions") or []:
            clean = {k: v for k, v in fd.items() if k != "jdy_widget"}
            if clean.get("type") == "detail_table" and clean.get("detail_table_columns"):
                clean["detail_table_columns"] = [
                    {k: v for k, v in c.items() if k != "jdy_widget"}
                    for c in clean["detail_table_columns"]
                ]
            defs.append(clean)
        # 新设计卡号：对齐简道云「部门编号-yyyyMMdd+两位日序（按部门编号分序列）」
        if t["key"] in ("scheme_management", "install_drawing_notice"):
            from app.domains.lowcode.dept_code import apply_design_card_serial_rules
            apply_design_card_serial_rules(defs)
            from app.domains.lowcode.base_lookups import patch_scheme_material_columns
            patch_scheme_material_columns(defs)
        # 安装图仍保留业务打分；方案管理已去掉三项分数
        if t["key"] == "install_drawing_notice":
            from app.domains.lowcode.biz_score import apply_biz_score_field_defs
            apply_biz_score_field_defs(defs)
        # 永久删除：前期沟通的设计员（文本）；方案管理去掉业务打分字段
        drop_ids = {"pre_designer_text"}
        if t["key"] == "scheme_management":
            drop_ids |= {
                "score_attitude", "score_progress", "score_skill",
                "score_total", "score_date",
            }
        defs = [f for f in defs if f.get("id") not in drop_ids]
        rules = [
            r for r in (pack.get("rule_definitions") or [])
            if r.get("target_field_id") not in drop_ids
            and not (set(r.get("target_field_ids") or []) & drop_ids)
        ]
        t["field_definitions"] = defs
        t["name"] = pack.get("name") or t["name"]
        t["rule_definitions"] = rules


_apply_drawing_jdy_fields()


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

