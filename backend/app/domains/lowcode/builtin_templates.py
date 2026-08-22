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
        "name": "合同图纸领用",
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
        "key": "shipment_notice",
        "name": "发货通知",
        "category": "发货",
        "icon": "CarOutlined",
        "description": (
            "对齐简道云销售中心「CRM-发货通知流程」"
            "(app=5de0b3e8… entry=5de5f57e…)。"
            "单据编号 24.1-+yyyyMMdd+四位日序。"
            "详见 docs/product/_jdy_shipment_notice_forms.md。"
        ),
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "xunhan_contract_review",
        "name": "迅焊公司合同评审",
        "category": "合同",
        "icon": "AuditOutlined",
        "description": (
            "对齐简道云销售中心「迅焊公司合同评审」"
            "(app=5de0b3e8… entry=67d3d515…)。"
            "流水号 24.2.3+yyyyMMdd+五位月序。"
            "详见 docs/product/_jdy_xunhan_contract_review_crm_forms.md。"
        ),
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "presale_service_notice",
        "name": "售前服务通知",
        "category": "图纸",
        "icon": "NotificationOutlined",
        "description": (
            "对齐简道云销售中心「售前服务通知流程」"
            "(app=5de0b3e8… entry=5e79b7e9…)。"
            "流水号 24.13-+yyyyMMdd+四位日序。"
            "详见 docs/product/_jdy_presale_service_notice_forms.md。"
        ),
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "prod_card_supplement",
        "name": "生产卡/补充流程",
        "category": "合同",
        "icon": "ContainerOutlined",
        "description": (
            "对齐简道云数据中心「生产卡/补充流程」。"
            "流程编号 1.2.8+五位不重置。字段见 docs/product/_jdy_prod_card_forms.md。"
        ),
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
        "description": (
            "对齐简道云数据中心「收款登记」。"
            "收款号 SKDJ-+五位不重置。字段见 docs/product/_jdy_payment_registration_forms.md。"
        ),
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
        "key": "pricing_checklist_hjqd",
        "name": "核价清单传递",
        "category": "研究院",
        "icon": "FileDoneOutlined",
        "description": (
            "对齐简道云中央研究院「核价清单传递流程HJQD」"
            "(app=58465841… entry=66763853…)。"
            "流水号 HJQD-+yyyyMMdd+五位不重置。"
            "详见 docs/product/_jdy_pricing_checklist_hjqd_forms.md。"
        ),
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "research_coop_card",
        "name": "中央研究院协同卡",
        "category": "研究院",
        "icon": "ApartmentOutlined",
        "description": (
            "对齐简道云中央研究院「中央研究院协同卡」"
            "(app=58465841… entry=63acddd2…)。"
            "流水号 6.19.1-+yyyyMMdd+两位日序。"
            "详见 docs/product/_jdy_research_coop_card_forms.md。"
        ),
        "field_definitions": [],
        "sync_fields": True,
    },
    # —— 客户服务部（售后低代码，与原生售后工单并存）——
    {
        "key": "cs_service_request",
        "name": "客户服务申请及反馈",
        "category": "售后",
        "icon": "CustomerServiceOutlined",
        "description": "对齐简道云客户服务部「客户服务申请及反馈」。与原生售后工单并存。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "cs_product_replace",
        "name": "售出产品更换（补发）",
        "category": "售后",
        "icon": "SwapOutlined",
        "description": "对齐简道云客户服务部「售出产品更换（补发）流程」。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "cs_product_return",
        "name": "售出产品/工具退回",
        "category": "售后",
        "icon": "RollbackOutlined",
        "description": "对齐简道云客户服务部「售出产品/工具退回流程SCCP/GJTH」。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "cs_loan_slip",
        "name": "客服借据",
        "category": "售后",
        "icon": "FileTextOutlined",
        "description": "对齐简道云客户服务部「客服借据」。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "cs_drawing_request",
        "name": "客服领图",
        "category": "售后",
        "icon": "FileImageOutlined",
        "description": "对齐简道云客户服务部「客服领图」(app=58e2fbc7… entry=63840316…)。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "cs_service_delay",
        "name": "客户服务延期申请",
        "category": "售后",
        "icon": "FieldTimeOutlined",
        "description": "对齐简道云客户服务部「客户服务延期申请」。",
        "field_definitions": [],
        "sync_fields": True,
    },
    {
        "key": "cs_correspondence",
        "name": "客服往来函件",
        "category": "售后",
        "icon": "MailOutlined",
        "description": "对齐简道云客户服务部「客服往来函件KFWLHJ」。",
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
            "年月/年段按取号当天（日期时间）。预填流水号可手改，只要对应表内未占用即可。"
            "合同登记从图纸编号下拉选用本表记录（选用的图纸号即合同号）。"
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
            {"id": "department", "type": "department", "label": "业务部门", "required": True},
            {
                "id": "drawing_no", "type": "auto_number", "label": "图纸编号",
                # 对齐简道云：预填流水号，允许手改
                "form_editable": True,
                "props": {
                    "manual_edit": True,
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
    {
        "key": "salesperson_region_map",
        "name": "业务员区域经理对照",
        "category": "合同",
        "icon": "TeamOutlined",
        "description": (
            "对齐简道云销售中心「业务员→区域经理/组长」对照表"
            "(formId=698151a0…)。"
            "合同评审/客服等选业务员后按本表自动回填区域经理/组长。"
        ),
        "sync_fields": True,
        "field_definitions": [
            {"id": "salesperson", "type": "person", "label": "业务员", "required": True},
            {"id": "region_manager", "type": "person", "label": "区域经理/组长", "required": True},
            {
                "id": "region",
                "type": "select",
                "label": "区域",
                "options": [
                    {"value": "华北区", "label": "华北区"},
                    {"value": "华东区", "label": "华东区"},
                    {"value": "华南区", "label": "华南区"},
                    {"value": "华西区", "label": "华西区"},
                    {"value": "新疆区域", "label": "新疆区域"},
                    {"value": "备品备件推进组", "label": "备品备件推进组"},
                    {"value": "循环经济组", "label": "循环经济组"},
                    {"value": "分布筛推进组", "label": "分布筛推进组"},
                    {"value": "战略推进组", "label": "战略推进组"},
                    {"value": "宝武系", "label": "宝武系"},
                    {"value": "裕华系", "label": "裕华系"},
                    {"value": "大包", "label": "大包"},
                ],
            },
            {"id": "remark", "type": "textarea", "label": "备注"},
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
    try:
        from app.domains.lowcode._pricing_checklist_hjqd_generated import PRICING_CHECKLIST_HJQD_JDY
    except Exception:
        PRICING_CHECKLIST_HJQD_JDY = {}
    try:
        from app.domains.lowcode._research_coop_card_generated import RESEARCH_COOP_CARD_JDY
    except Exception:
        RESEARCH_COOP_CARD_JDY = {}
    try:
        from app.domains.lowcode._customer_service_jdy_generated import CUSTOMER_SERVICE_JDY
    except Exception:
        CUSTOMER_SERVICE_JDY = {}
    try:
        from app.domains.lowcode._presale_service_notice_generated import PRESALE_SERVICE_NOTICE_JDY
    except Exception:
        PRESALE_SERVICE_NOTICE_JDY = {}
    try:
        from app.domains.lowcode._shipment_notice_generated import SHIPMENT_NOTICE_JDY
    except Exception:
        SHIPMENT_NOTICE_JDY = {}
    try:
        from app.domains.lowcode._xunhan_contract_review_generated import XUNHAN_CONTRACT_REVIEW_JDY
    except Exception:
        XUNHAN_CONTRACT_REVIEW_JDY = {}
    packs = {
        **DRAWING_JDY, **SCHEME_MANAGEMENT_JDY, **PROD_CARD_JDY,
        **INVOICE_PAYMENT_JDY, **QUOTE_MANAGEMENT_JDY, **PRICING_CHECKLIST_HJQD_JDY,
        **RESEARCH_COOP_CARD_JDY, **CUSTOMER_SERVICE_JDY, **PRESALE_SERVICE_NOTICE_JDY,
        **SHIPMENT_NOTICE_JDY, **XUNHAN_CONTRACT_REVIEW_JDY,
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
        # 流水号与设计卡号相互独立，不可混用
        if t["key"] in ("scheme_management", "install_drawing_notice"):
            from app.domains.lowcode.dept_code import (
                apply_design_card_serial_rules,
                apply_install_drawing_serial_no_field,
                apply_scheme_serial_no_field,
            )
            apply_design_card_serial_rules(defs)
            if t["key"] == "scheme_management":
                apply_scheme_serial_no_field(defs)
            else:
                apply_install_drawing_serial_no_field(defs)
            from app.domains.lowcode.base_lookups import patch_scheme_material_columns
            patch_scheme_material_columns(defs)
        # 合同图纸领用：流水号 / 默认值 / 合同关联 / 去掉文本桩
        if t["key"] == "drawing_requisition":
            from app.domains.lowcode.drawing_requisition_fields import (
                apply_drawing_requisition_fields,
            )
            apply_drawing_requisition_fields(defs)
        # 客服领图：指派人选范围 / 下单日期对齐图纸领用·安装图
        if t["key"] == "cs_drawing_request":
            from app.domains.lowcode.cs_drawing_request_fields import (
                apply_cs_drawing_request_fields,
            )
            apply_cs_drawing_request_fields(defs)
        # 安装图：创建/审批阶段 + 业务打分（方案管理已去掉三项分数）
        if t["key"] == "install_drawing_notice":
            from app.domains.lowcode.install_drawing_notice_fields import (
                apply_install_drawing_notice_fields,
            )
            apply_install_drawing_notice_fields(defs)
        if t["key"] == "prod_card_supplement":
            from app.domains.lowcode.prod_card_contract_fill import apply_prod_card_contract_pick_fields
            apply_prod_card_contract_pick_fields(defs)
        if t["key"] == "payment_registration":
            from app.domains.lowcode.payment_registration_fields import apply_payment_registration_fields
            apply_payment_registration_fields(defs)
        if t["key"] == "invoice_application":
            from app.domains.lowcode.invoice_application_fields import apply_invoice_application_fields
            apply_invoice_application_fields(defs)
        if t["key"] == "quote_management":
            from app.domains.lowcode.quote_management_fields import apply_quote_management_fields
            apply_quote_management_fields(defs)
        if t["key"] == "pricing_checklist_hjqd":
            from app.domains.lowcode.pricing_checklist_fields import apply_pricing_checklist_fields
            apply_pricing_checklist_fields(defs)
            _FINANCE_DOWNLOAD = ["finance", "finance_manager"]
            for f in defs:
                if isinstance(f, dict) and f.get("id") in ("attachments", "images"):
                    f["download_roles"] = list(_FINANCE_DOWNLOAD)
        if t["key"] == "presale_service_notice":
            from app.domains.lowcode.presale_service_notice_fields import apply_presale_service_notice_fields
            apply_presale_service_notice_fields(defs)
        if t["key"] == "shipment_notice":
            from app.domains.lowcode.shipment_notice_fields import apply_shipment_notice_fields
            apply_shipment_notice_fields(defs)
        # 永久删除：文本桩字段（保留选人）；方案管理去掉业务打分字段
        drop_ids = {"pre_designer_text"}
        if t["key"] == "drawing_requisition":
            drop_ids |= {"order_person_text", "designer_text", "need_decrypt_note"}
        if t["key"] == "install_drawing_notice":
            drop_ids |= {
                "order_person_text",
                "score_attitude", "score_progress", "score_skill",
                "score_total", "score_date", "remark",
            }
        if t["key"] == "scheme_management":
            drop_ids |= {
                "score_attitude", "score_progress", "score_skill",
                "score_total", "score_date",
                "order_person_text", "designer_text",
            }
            for f in defs:
                if not isinstance(f, dict):
                    continue
                if f.get("id") in ("offices", "offices_multi"):
                    f["type"] = "department_multi"
                    f["label"] = "科室"
            from app.domains.lowcode.pickable_scope import apply_scheme_design_person_scope_rules
            apply_scheme_design_person_scope_rules(defs)
            for f in defs:
                if not isinstance(f, dict):
                    continue
                if f.get("id") == "order_date":
                    f["type"] = "date"
                    props = dict(f.get("props") or {})
                    props["show_time"] = False
                    props["date_only"] = True
                    props.pop("default_today", None)
                    props["default_today_on_approve"] = True
                    f["props"] = props
                if f.get("id") == "contract_no":
                    f["type"] = "contract"
                    f["label"] = "合同号"
                    f["description"] = "从合同管理中选择；按图纸编号搜索，选项以图纸编号显示。"
        defs = [f for f in defs if f.get("id") not in drop_ids]
        rules = [
            r for r in (pack.get("rule_definitions") or [])
            if r.get("target_field_id") not in drop_ids
            and not (set(r.get("target_field_ids") or []) & drop_ids)
        ]
        if t["key"] == "cs_drawing_request":
            from app.domains.lowcode.cs_drawing_request_fields import (
                apply_cs_drawing_request_rules,
            )
            rules = apply_cs_drawing_request_rules(rules)
        if t["key"] == "prod_card_supplement":
            from app.domains.lowcode.prod_card_contract_fill import (
                apply_prod_card_supplement_rules,
            )
            rules = apply_prod_card_supplement_rules(rules)
        if t["key"] in ("scheme_management", "install_drawing_notice"):
            from app.domains.lowcode.base_lookups import remap_scheme_material_rule_triggers
            remap_scheme_material_rule_triggers(rules)
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

