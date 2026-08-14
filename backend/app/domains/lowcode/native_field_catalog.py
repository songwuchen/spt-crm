"""业务实体「原生字段」目录 —— 让内置字段也能被租户配置必填/显隐/只读/字段级权限。

背景：扩展字段(custom_fields_json)早就能配 required / visible_roles / edit_roles 和条件规则，
原生字段(表上的真实列)却全部硬编码在前端表单里，租户改不了。本目录把原生字段声明成与扩展
字段同构的 FieldDefinition，于是两者共用一套设计器、一套规则引擎、一套校验，规则条件也能
跨原生与扩展字段互相引用（例如「国别=国外时，显示扩展字段 报关方式」）。

关键约束：
- 目录是 id/type 的唯一事实源。租户的改动以「覆盖项」形式存在版本里，读取时按本目录重建，
  因此租户永远无法把原生字段删掉、改 id 或改类型 —— 那会直接写坏业务列的映射。
- system_required=True 表示数据库层 NOT NULL 或业务强依赖，租户不可改为非必填。
- 值不进 custom_fields_json：原生字段仍读写自己的列，只有「配置」走表单引擎。

新增实体时在 CATALOG 里加一项即可；字段的 label 用作默认显示名，租户可覆盖。
"""
from __future__ import annotations

from typing import Any

# 租户可覆盖的属性白名单。id/type 不在其中 —— 它们决定了字段与业务列的绑定关系。
OVERRIDABLE_KEYS = {
    "label", "placeholder", "description", "required", "span",
    "visible_roles", "unmask_roles", "edit_roles", "props",
    # 下拉/单选/多选选项：设计器可改，发布后业务页与 FormRenderer 同口径
    "options",
    # 填写阶段：发起可见 vs 仅审批填写（对齐简道云 optAuth）
    "available_on_create", "fill_stage", "form_editable",
    # 明细子表列：设计器可改列结构（合同明细/收款计划与通用 detail_table 共用）
    "detail_table_columns",
}
# props 里允许覆盖的子键（其余 props 由目录决定，避免租户塞进影响渲染的任意配置）
OVERRIDABLE_PROP_KEYS = {"hidden", "readonly"}


def _f(fid: str, label: str, ftype: str = "text", *, system_required: bool = False,
       default_required: bool = False, options_source: str | None = None,
       companions: tuple[str, ...] = (), form_editable: bool = True,
       available_on_create: bool = True,
       fill_stage: str | None = None,
       json_storage: str | None = None,
       entity_storage: str | None = None,
       detail_table_columns: list[dict[str, Any]] | None = None,
       options: list[dict[str, str]] | None = None,
       **props: Any) -> dict[str, Any]:
    """声明一个原生字段。

    system_required: 数据库 NOT NULL 或业务强依赖，恒为必填且租户不可改。
    default_required: 出厂默认必填，但租户可以改成非必填（用于保留改造前表单里硬编码的必填项）。
    options_source: 指向数据字典 dict_type 或内置枚举，供设计器展示可选值。
    options: 静态选项（设计器预览 / FormRenderer 用）；与 options_source 可并存。
    companions: 该字段的「派生显示键」……
    json_storage: 值落在某 JSON 列内的 key（如 registration_json.xxx）。
    entity_storage: 整字段值落在业务表/版本的 JSON 列（如 key_clauses_json），用于 detail_table。
    detail_table_columns: 明细子表列定义。
    """
    fd: dict[str, Any] = {
        "id": fid, "label": label, "type": ftype,
        "native": True,
        "system_required": system_required,
        "required": system_required or default_required,
        "form_editable": form_editable,
        "available_on_create": available_on_create,
    }
    if fill_stage:
        fd["fill_stage"] = fill_stage
    elif available_on_create is False:
        fd["fill_stage"] = "approver"
    if companions:
        fd["companions"] = list(companions)
    if options_source:
        fd["options_source"] = options_source
    if json_storage:
        fd["json_storage"] = json_storage
    if entity_storage:
        fd["entity_storage"] = entity_storage
    if detail_table_columns is not None:
        fd["detail_table_columns"] = detail_table_columns
    if options:
        fd["options"] = list(options)
    if props:
        fd["props"] = props
    return fd


def _col(
    cid: str, label: str, ctype: str = "text", *,
    options: list[dict[str, str]] | None = None,
    required: bool = False,
    **props: Any,
) -> dict[str, Any]:
    """明细子表列。业务扩展 props：aliases / show_when / computed / width / align / percent。

    目录列默认 system_column=True，设计器不可删 id（可改标签/选项）；租户自增列无此标记。
    """
    col_props = {"system_column": True, **props}
    fd: dict[str, Any] = {
        "id": cid, "label": label, "type": ctype, "required": required, "props": col_props,
    }
    if options:
        fd["options"] = list(options)
    return fd


_YES_NO = [{"value": "是", "label": "是"}, {"value": "否", "label": "否"}]

_LINE_PRODUCT_TYPES = [
    {"value": v, "label": v} for v in (
        "复频筛", "高幅筛", "其他筛分设备", "输送设备", "破碎设备",
        "除尘设备", "污水净化设备", "智能装备", "其他",
    )
]
_LINE_ELEC_CTRL = [
    {"value": v, "label": v} for v in (
        "含电控电缆", "含电控不含电缆", "不含电控不含电缆", "不含电控含电缆",
    )
]
_PAY_KINDS = [
    {"value": v, "label": v} for v in (
        "预付", "发货", "到货", "验收", "调试", "质保", "其他",
    )
]

_FX_SHOW = {"field": "is_fx", "equals": ["是"]}

_CONTRACT_LINE_COLUMNS: list[dict[str, Any]] = [
    _col("is_fx", "是否外币合同", "radio", options=_YES_NO,
         aliases=["_widget_1621411268784"], width=120, align="center"),
    _col("product_type", "产品类型", "select", options=_LINE_PRODUCT_TYPES,
         aliases=["_widget_1561431500162"], width=130),
    _col("name", "产品名称", aliases=["_widget_1561431500376"], width=140),
    _col("spec", "规格型号", aliases=["_widget_1561431500392"], width=120),
    _col("unit", "单位", aliases=["_widget_1561431500419"], width=70, align="center"),
    _col("qty", "数量", "number", aliases=["_widget_1561431500458"], width=90, align="right"),
    _col("fx_price", "外币单价", "number", aliases=["_widget_1621411268153"],
         width=110, align="right", show_when=_FX_SHOW),
    _col("fx_rate", "汇率", "number", aliases=["_widget_1621411269220"],
         width=90, align="right", show_when=_FX_SHOW),
    _col("price", "单价", "amount", aliases=["_widget_1561431500490"], width=120, align="right"),
    _col("amount", "总价", "amount", aliases=["_widget_1561431500514"],
         width=130, align="right", computed=True),
    _col("fx_amount", "外币总价", "number", aliases=["_widget_1621411268210"],
         width=120, align="right", computed=True, show_when=_FX_SHOW),
    _col("elec_ctrl", "电控装置", "select", options=_LINE_ELEC_CTRL,
         aliases=["_widget_1561431500595"], width=150),
    _col("standard", "技术参数及要求", aliases=["_widget_1565223122750"], width=160),
    _col("line_remark", "备注", aliases=["_widget_1697420581927"], width=140),
]

_CONTRACT_PAY_COLUMNS: list[dict[str, Any]] = [
    _col("due_date", "日期时间", "date", aliases=["_widget_1661242797064"], width=150),
    _col("kind", "付款方式", "select", options=_PAY_KINDS,
         aliases=["_widget_1561431500818", "付款方式", "款项性质"], width=110),
    _col("ratio", "付款比例", "number", aliases=["_widget_1561431500832", "付款比例（%）"],
         width=110, align="right", percent=True),
    _col("amount", "付款金额", "amount", aliases=["_widget_1561431500855", "付款金额"],
         width=130, align="right"),
    _col("remind", "是否提醒", "radio", options=_YES_NO,
         aliases=["_widget_1665380028160", "是否提醒"], width=110, align="center"),
    _col("note", "消息辅助", aliases=["_widget_1665380027757"], width=140),
]


# 已把表单接入 PolicyItem 的实体。只有这些实体的 required/条件显隐会在表单上生效；
# 其余实体目前只享用读取路径的隐藏/脱敏（列表、详情、导出）。
# 接入某实体表单后，把它加进来，test_catalog_fields_all_have_a_form_control 会开始校验对齐。
FORM_WIRED: set[str] = {
    "lead", "customer", "contact", "project", "contract", "order",
    "service_ticket", "payment", "solution",
}


# entity_type -> 该实体表单上可配置的原生字段（顺序即设计器/表单默认顺序）
CATALOG: dict[str, list[dict[str, Any]]] = {
    "lead": [
        # ---- 申报信息（对齐简道云销售中心「申报信息」）----
        # 必填策略：JDY allowBlank=false 的字段在 LeadForm 用 PolicyItem 硬必填；
        # 目录仅对 title/company_name 设出厂必填，避免 OpenAPI/pytest 简写建档被大批量拦住
        #（与 customer 开关字段同理）。条件必填/显隐见 SYSTEM_RULES。
        _f("category", "来源", "radio", options_source="enum:lead_category",
           options=[{"value": "self_reported", "label": "自报"}, {"value": "distributed", "label": "分发"}]),
        _f("title", "项目名称", system_required=True),
        _f("company_name", "公司名称", default_required=True),
        _f("customer_type", "客户类型", "select", options_source="dict:customer_type",
           options=[{"value": v, "label": v} for v in (
               "终端客户-央企/国企", "终端客户-大型民企（注册资本10亿以上）",
               "终端客户-一般民企", "设计院", "总包商", "配套商、贸易商", "其他")]),
        _f("region", "详细地址"),
        _f("has_internal_conflict", "是否内部冲突", "radio", options=_YES_NO),
        # 冲突备注：JDY allowBlank=false，仅「是」时显示；必填由 SYSTEM_RULES 条件注入
        _f("conflict_note", "备注：请示部门经理的结果"),
        _f("industry", "行业", "select", options_source="dict:industry",
           options=[{"value": v, "label": v} for v in (
               "筛分分选-冶金", "筛分分选-矿山", "筛分分选-砂石", "筛分分选-焦化",
               "筛分分选-煤炭", "筛分分选-电力", "筛分分选-化工", "筛分分选-医药",
               "筛分分选-食品", "筛分分选-备件", "循环经济", "废钢利用",
               "智能化大宗物料管理")]),
        _f("bid_result", "中标情况", "select", available_on_create=False,
           options=[{"value": v, "label": v} for v in (
               "中标", "结果未出", "项目取消", "项目延期", "落标", "流标", "未参与")]),
        _f("bid_fail_reason", "原因", "select", available_on_create=False,
           options=[{"value": v, "label": v} for v in (
               "价格原因：价格高、最低价中标",
               "内定：客户不愿意更换厂家、客户内部操作了、走形式、内定中标单位了",
               "资质原因：需要煤安证、矿安证、业主要求进口品牌；业绩达不到",
               "技术原因：技术参数不符合、参数达不到现场要求、筛分效率达不到、功率偏高客户不同意、技术没达到对方要求、客户要求技术是国际标准",
               "客户现场原因：现场空间不足",
               "质保原因：质保期达不到",
               "付款方式偏离：客户不接受咱的付款方式",
               "工期原因：要求交货时间达不到",
               "客户不透露")]),
        _f("country_type", "国别", "radio", options_source="enum:lead_country_type",
           options=[{"value": "domestic", "label": "国内"}, {"value": "overseas", "label": "国外"}]),
        _f("country_name", "国家"),
        _f("entrust_status", "委托状态", "radio",
           options=[{"value": "已开", "label": "已开"}, {"value": "未开", "label": "未开"}]),
        _f("entrust_issued_at", "委托开具日期", "datetime"),
        _f("entrust_term", "委托期限"),
        _f("department_id", "部门", "department", companions=("department_name",)),
        _f("reporter_id", "申报人", "person", companions=("reporter_name",)),
        _f("reported_at", "申报时间", "datetime"),
        _f("owner_id", "负责人", "person", companions=("owner_name",)),
        _f("project_activity", "项目动态", "radio",
           options=[{"value": v, "label": v} for v in (
               "技术交流", "出方案", "报价", "投标", "拟建")]),
        _f("demand_summary", "备注1（线索内容）", "textarea"),
        # ---- 业务反馈项目详情（跟进时填写，非发起必填）----
        _f("project_recent", "项目近况", available_on_create=False, fill_stage="followup"),
        _f("follow_progress", "跟进进度", available_on_create=False, fill_stage="followup"),
        _f("site_visit", "实地拜访情况", available_on_create=False, fill_stage="followup"),
        _f("report_project_status", "项目状态", "radio",
           available_on_create=False, fill_stage="followup",
           options=[{"value": v, "label": v} for v in (
               "进行中", "暂停", "取消", "落标", "中标", "已签合同")]),
        # ---- 评估信息（审批节点 / 情报裁定写入；销售表单不展示）----
        _f("customer_newness", "客户类型（新/老）", "radio",
           form_editable=False, available_on_create=False, fill_stage="approver",
           options=[{"value": "new", "label": "新"}, {"value": "old", "label": "老"}]),
        _f("reject_reason", "回退原因", "textarea",
           form_editable=False, available_on_create=False, fill_stage="approver"),
        _f("assess_remark", "备注2", "textarea",
           form_editable=False, available_on_create=False, fill_stage="approver"),
        _f("review_opinion", "操作意见", "textarea",
           form_editable=False, available_on_create=False, fill_stage="approver"),
        # ---- 其他（CRM 扩展，不挡报备主路径）----
        _f("source", "线索来源", "select", options_source="dict:lead_source"),
        _f("biz_date", "业务日期", "date"),
        _f("contact_name", "联系人"),
        _f("contact_phone", "联系电话"),
        _f("contact_email", "联系邮箱"),
        _f("remark", "备注", "textarea"),
    ],

    # 客户表单已接 PolicyItem（FORM_WIRED）；系统显隐规则见 SYSTEM_RULES["customer"]。
    "customer": [
        # ---- 开关：表单侧 PolicyItem 硬必填；目录不设 default_required，避免 API/测试
        # 只传 name 建客户时被「开关未填」拦住（开关缺省时内贸分区也未展开）。
        _f("is_smart_filing", "是否智能化客户信息备案", "radio",
           options=[{"value": True, "label": "是"}, {"value": False, "label": "否"}]),
        _f("is_foreign_trade", "是否外贸客户", "radio",
           options=[{"value": True, "label": "是"}, {"value": False, "label": "否"}]),
        _f("need_info_distribute", "信息分发-客户", "radio",
           options=[{"value": True, "label": "是"}, {"value": False, "label": "否"}]),
        # ---- 基本信息（始终可见）----
        _f("name", "客户名称", system_required=True),
        _f("customer_code", "客户编号"),
        # 行业/地址：同样由表单硬必填；API 简写建档不强制
        _f("industry", "所属行业", "radio", options_source="dict:industry",
           options=[{"value": v, "label": v} for v in (
               "工业升级", "循环经济", "基建民生", "技术改造", "其他")]),
        _f("scale_level", "企业规模", "select", options_source="dict:scale_level",
           options=[{"value": v, "label": v} for v in ("微型", "小型", "中型", "大型", "特大型")]),
        _f("address", "详细地址"),
        _f("website", "主页"),
        _f("source", "客户来源", "select", options_source="dict:customer_source",
           options=[
               {"value": "expo", "label": "展会"},
               {"value": "referral", "label": "转介绍"},
               {"value": "ad", "label": "广告"},
               {"value": "inbound", "label": "官网/入站"},
               {"value": "partner", "label": "合作伙伴"},
               {"value": "call", "label": "电话"},
               {"value": "阿里", "label": "阿里"},
               {"value": "QQ", "label": "QQ"},
               {"value": "TQ", "label": "TQ"},
               {"value": "ETW", "label": "ETW"},
               {"value": "GM", "label": "GM"},
               {"value": "Trade2cn", "label": "Trade2cn"},
               {"value": "Tradekey", "label": "Tradekey"},
               {"value": "Direct Industry", "label": "Direct Industry"},
               {"value": "搜索", "label": "搜索"},
               {"value": "康帕斯", "label": "康帕斯"},
               {"value": "LINKEDIN", "label": "LINKEDIN"},
               {"value": "其他", "label": "其他"},
           ]),
        # ---- 内贸档案（外贸=否时显示；显隐隐藏时规则引擎会去掉必填）----
        _f("registered_capital", "注册资金（万元）", "amount", default_required=True),
        _f("paid_in_capital", "实缴资本（万元）", "amount", default_required=True),
        _f("founded_year", "成立年份", "number", default_required=True),
        _f("parent_company_note", "母公司或者控股公司情况及性质说明", "textarea", default_required=True),
        _f("customer_nature", "客户性质", "radio", default_required=True,
           options=[{"value": v, "label": v} for v in ("一般民企", "国企控股", "国有企业", "上市公司", "其他")]),
        _f("customer_relation", "客户关系", "radio", default_required=True,
           options=[{"value": "直接关系", "label": "直接关系"}, {"value": "间接关系", "label": "间接关系"}]),
        _f("level", "客户类型", "radio", options_source="dict:customer_level", default_required=True,
           options=[{"value": v, "label": v} for v in ("A", "B", "C", "D")]),
        _f("primary_contact_title", "主联系人职位", "radio", default_required=True,
           options=[{"value": v, "label": v} for v in (
               "一般员工", "主管级别", "部门经理级别", "副总经理级别", "总经理及董事长级别")]),
        _f("wage_insurance_status", "客户工资及保险情况", "radio", default_required=True,
           options=[{"value": v, "label": v} for v in ("正常", "正常有拖欠", "非正常")]),
        # ---- 开票（外贸=否时显示）----
        _f("taxpayer_id", "纳税人识别号", default_required=True),
        _f("invoice_address_phone", "地址电话"),
        _f("bank_account", "开户行帐号"),
        _f("is_company_customer", "是否公司客户", "radio", default_required=True,
           options=[{"value": True, "label": "是"}, {"value": False, "label": "否"}]),
        # ---- 外贸（外贸=是时显示；简道云标签带*但 allowBlank=true，默认非必填）----
        _f("region", "国家/地区"),
        _f("country", "国别"),
        _f("short_name", "客户简称"),
        _f("foreign_customer_code", "客户代码"),
        _f("foreign_customer_type", "客户类型（外贸）", "select",
           options=[{"value": v, "label": v} for v in (
               "合作客户", "潜在客户", "合作供应商", "潜在供应商", "合作货贷商",
               "验货公司", "合作会展商", "合作推广商", "潜在推广商", "潜在货代商")]),
        _f("focus_product", "关注产品", "select",
           options=[{"value": v, "label": v} for v in (
               "旋振筛", "检验筛", "振动筛", "高幅筛", "熔剂筛", "节肢筛", "圆振筛", "直线筛",
               "球团筛", "香蕉筛", "弧形筛", "脱泥脱介筛", "轻型筛", "落砂机", "给料机",
               "输送机", "破碎机", "破碎筛分生产线", "备件", "其他")]),
        _f("customer_email", "邮箱"),
        _f("main_products_json", "主营产品", "checkbox",
           options=[{"value": v, "label": v} for v in (
               "冶金", "煤炭", "矿山", "焦化", "电力", "食品", "医药", "化工",
               "砂石骨料，制砂", "水处理")]),
        # ---- 智能化备案（智能化=是时显示）----
        _f("legal_person", "企业法人", default_required=True),
        _f("headcount", "企业员工人数", "number", default_required=True),
        _f("smart_industry_category", "所属行业分类", default_required=True),
        _f("annual_run_days", "年运行天数"),
        _f("floor_area", "占地面积"),
        _f("financial_status", "企业财务状况", "textarea"),
        _f("business_status", "企业经营状况", "textarea"),
        _f("annual_power_usage", "年用电量"),
        _f("daily_operate_hours", "日运营小时数"),
        # ---- 商机 / 其它 ----
        _f("budget_amount", "预算金额", "amount"),
        _f("demand", "需求描述", "textarea"),
        _f("expected_purchase_date", "预计采购日期", "date"),
        _f("postal_code", "邮编"),
        _f("remark", "备注", "textarea"),
        # 业务员：表单必填；API 创建时会回落到当前用户，故目录不设 default_required
        _f("owner_id", "业务员", "person", companions=("owner_name",)),
    ],
    "contact": [
        _f("name", "姓名", system_required=True),
        _f("title", "职务"),
        _f("department", "所在部门"),
        _f("phone", "电话"),
        _f("mobile", "手机"),
        _f("email", "邮箱"),
        _f("remark", "备注", "textarea"),
    ],
    "project": [
        _f("name", "商机名称", system_required=True),
        _f("lead_code", "来源线索编号", form_editable=False, available_on_create=False),
        _f("amount_expect", "预期金额", "amount"),
        _f("probability", "赢单概率", "number"),
        _f("close_date_expect", "预计成交日期", "date"),
        _f("payment_method", "付款方式"),
        _f("remark", "备注", "textarea"),
    ],
    "contract": [
        # 顺序对齐 frontend CONTRACT_REGISTRATION_SECTIONS（基本信息 → 产品 → 收款 → 其他 → 物流 → 验收）
        # ---- 基本信息（表列）----
        _f("card_date", "下卡日期", "date", default_required=True),
        _f("department_id", "部门", "department", companions=("department_name",),
           default_required=True),
        _f("assignee_id", "业务人员", "person", companions=("assignee_name",),
           default_required=True),
        _f("change_type", "合同状态", "select", options_source="enum:contract_change_type",
           default_required=True,
           options=[{"value": "new", "label": "新增"}, {"value": "change", "label": "变动"}]),
        _f("acquire_method", "合同获取信息方式", "radio", default_required=True,
           options=[{"value": "公开招标", "label": "公开招标"},
                    {"value": "邀请招标", "label": "邀请招标"},
                    {"value": "协商一致", "label": "协商一致"}]),
        # ---- 基本信息（registration_json）----
        _f("customer_code", "客户编号", json_storage="registration_json"),
        _f("change_reason", "变动原因", json_storage="registration_json"),
        _f("review_sn", "合同/项目评审流水号", json_storage="registration_json"),
        _f("review_sn_xm", "小萌合同评审流水号", json_storage="registration_json"),
        _f("factory_no", "出厂编号", json_storage="registration_json"),
        # ---- 合同产品信息（表列）----
        _f("order_date", "订货日期", "date", default_required=True),
        _f("contract_no", "合同号", form_editable=True, available_on_create=True,
           system_required=True),  # 业务手填，不可被租户降为非必填
        _f("drawing_no", "图纸编号", form_editable=False, available_on_create=False, default_required=False),
        _f("peer_contract_no", "对方合同号"),
        _f("amount_total", "合同总金额", "amount", default_required=True),
        # 合同明细子表：值存版本 key_clauses_json；列可在设计器覆盖
        _f("line_items", "合同明细", "detail_table",
           entity_storage="key_clauses_json",
           detail_table_columns=_CONTRACT_LINE_COLUMNS),
        # ---- 合同产品信息（registration_json）----
        _f("contract_type", "合同类型", "radio", json_storage="registration_json",
           available_on_create=False, default_required=False, fill_stage="approver",
           options=[{"value": "正式", "label": "正式"}, {"value": "非正式", "label": "非正式"}]),
        _f("project_name", "项目名称", json_storage="registration_json"),
        _f("tax_included", "是否含税", "radio", json_storage="registration_json",
           default_required=True, options=_YES_NO),
        _f("is_export", "设备是否出口", "radio", json_storage="registration_json",
           default_required=True, options=_YES_NO),
        _f("need_install", "是否需要安装", "radio", json_storage="registration_json",
           default_required=True,
           options=[{"value": "不需要安装", "label": "不需要安装"},
                    {"value": "指导安装", "label": "指导安装"},
                    {"value": "现场安装", "label": "现场安装"},
                    {"value": "拆旧装新", "label": "拆旧装新"}]),
        _f("info_complete", "信息是否齐全", "radio", json_storage="registration_json",
           default_required=True, options=_YES_NO),
        _f("missing_items", "缺少项", "checkbox", json_storage="registration_json",
           options=[{"value": "联系人", "label": "联系人"}, {"value": "联系方式", "label": "联系方式"},
                    {"value": "邮箱", "label": "邮箱"}, {"value": "地址", "label": "地址"}]),
        _f("info_incomplete_note", "信息不齐全备注", "textarea",
           json_storage="registration_json"),
        _f("export_type", "出口类型", json_storage="registration_json"),
        _f("contract_form", "合同形式", "radio", json_storage="registration_json",
           default_required=True,
           options=[{"value": "正式合同", "label": "正式合同"},
                    {"value": "非正式合同", "label": "非正式合同"},
                    {"value": "年标合同，订单无章", "label": "年标合同，订单无章"},
                    {"value": "年标合同，订单有章", "label": "年标合同，订单有章"},
                    {"value": "抖店", "label": "抖店"}]),
        _f("standard_delivery", "是否标准交付", "radio", json_storage="registration_json",
           options=_YES_NO),
        _f("delivery_mode", "方式", "radio", json_storage="registration_json",
           options=[{"value": "YZO", "label": "YZO"}, {"value": "YZS", "label": "YZS"},
                    {"value": "YZO和YZS", "label": "YZO和YZS"}]),
        _f("is_rotary_sieve", "是否为旋振筛", "radio", json_storage="registration_json",
           options=_YES_NO),
        _f("fill_code", "填写代码", json_storage="registration_json"),
        _f("purchasers", "采购员", json_storage="registration_json"),
        _f("inspectors", "质检员", json_storage="registration_json"),
        _f("tech_requirements", "技术参数及要求", "textarea",
           json_storage="registration_json"),
        _f("packaging", "包装情况", json_storage="registration_json"),
        _f("paint_req", "油漆要求", "radio", json_storage="registration_json",
           options=[{"value": "有协议指定要求", "label": "有协议指定要求"},
                    {"value": "待定", "label": "待定"}, {"value": "企标", "label": "企标"},
                    {"value": "参考某合同，请在备注填写所参考的合同号",
                     "label": "参考某合同，请在备注填写所参考的合同号"},
                    {"value": "其他", "label": "其他"}]),
        _f("workload", "工作量", "radio", json_storage="registration_json",
           options=[{"value": "设备", "label": "设备"}, {"value": "备件", "label": "备件"},
                    {"value": "电机", "label": "电机"}, {"value": "出口", "label": "出口"}]),
        # ---- 合同收款信息 ----
        _f("payment_forms", "付款形式", "checkbox", json_storage="registration_json",
           default_required=True,
           options=[{"value": "银承", "label": "银承"}, {"value": "商承", "label": "商承"},
                    {"value": "电汇", "label": "电汇"}, {"value": "现金", "label": "现金"}]),
        _f("payment_desc", "付款方式文字描述", json_storage="registration_json"),
        # 收款计划子表：值存合同 payment_terms_json
        _f("payment_terms", "收款计划", "detail_table",
           entity_storage="payment_terms_json",
           detail_table_columns=_CONTRACT_PAY_COLUMNS),
        _f("delivery_date", "合同交货期", "date", default_required=True),
        _f("delivery_clause", "交货期条款", json_storage="registration_json"),
        _f("warranty_period", "质保期限", json_storage="registration_json"),
        _f("warranty_amount", "质保金额", "amount", json_storage="registration_json"),
        _f("end_date", "到期日期", "date"),
        # ---- 合同其他信息 ----
        _f("industry", "行业分类", "select", json_storage="registration_json",
           default_required=True,
           options=[{"value": "工业升级", "label": "工业升级"},
                    {"value": "循环经济", "label": "循环经济"},
                    {"value": "基建民生", "label": "基建民生"},
                    {"value": "技术运营", "label": "技术运营"},
                    {"value": "其他", "label": "其他"}]),
        _f("region", "地区", "select", json_storage="registration_json",
           default_required=True,
           options=[{"value": "东北", "label": "东北"}, {"value": "华北", "label": "华北"},
                    {"value": "华东", "label": "华东"}, {"value": "华南", "label": "华南"},
                    {"value": "华中", "label": "华中"}, {"value": "西南", "label": "西南"},
                    {"value": "西北", "label": "西北"}, {"value": "出口", "label": "出口"}]),
        _f("application_field", "应用领域", "select", json_storage="registration_json"),
        _f("application_material", "应用物料", "select", json_storage="registration_json"),
        _f("has_intelligence", "是否含智能化", "radio", json_storage="registration_json",
           default_required=True, options=_YES_NO),
        _f("smart_points", "智能点", "checkbox", json_storage="registration_json",
           options=[{"value": "远程监控", "label": "远程监控"},
                    {"value": "智能润滑", "label": "智能润滑"},
                    {"value": "移动称量", "label": "移动称量"},
                    {"value": "视频监控", "label": "视频监控"},
                    {"value": "抑尘系统", "label": "抑尘系统"},
                    {"value": "产线自动化", "label": "产线自动化"},
                    {"value": "其他", "label": "其他"}]),
        _f("remark", "备注", "textarea", json_storage="registration_json"),
        _f("special_note", "特别提醒", json_storage="registration_json"),
        _f("note_date", "日期时间", "date", json_storage="registration_json"),
        # ---- 运费 / 地址 / 发货 ----
        _f("freight_payer", "运费承担方", "radio", json_storage="registration_json",
           default_required=True,
           options=[{"value": "我方", "label": "我方"}, {"value": "需方", "label": "需方"}]),
        _f("contract_address", "合同约定地址", json_storage="registration_json"),
        _f("ship_address", "发货地址", json_storage="registration_json"),
        _f("ship_status", "发货状态", json_storage="registration_json"),
        # ---- 验收（简道云：财务审核节点填写，创建不填）----
        _f("accept_method", "验收方式", "radio", json_storage="registration_json",
           available_on_create=False, default_required=False, fill_stage="approver",
           options=[{"value": "货到签收", "label": "货到签收"},
                    {"value": "指导安装不含验收", "label": "指导安装不含验收"},
                    {"value": "货到验收", "label": "货到验收"},
                    {"value": "指导安装含验收", "label": "指导安装含验收"},
                    {"value": "安装调试", "label": "安装调试"}]),
        _f("accept_materials", "验收所需资料", json_storage="registration_json",
           available_on_create=False, default_required=False, fill_stage="approver"),
        _f("accept_date", "验收日期", "date", json_storage="registration_json",
           available_on_create=False, default_required=False, fill_stage="approver"),
        _f("signed_date", "签订日期", "date", form_editable=False),
    ],
    # 报价的敏感字段(margin_rate/discount_total/cost_est)在 quote_versions / quote_lines /
    # cost_snapshots 上，不在 quotes 主表，本目录够不着 —— 那部分继续由按权限脱敏的
    # app/common/field_mask.py 负责（它本就是为这类嵌套响应体设计的）。
    "quote": [
        _f("quote_no", "报价单号", form_editable=False),  # 自动生成，表单上无输入项
    ],
    "service_ticket": [
        _f("priority", "优先级", "select", options_source="enum:ticket_priority"),
        _f("description", "问题描述", "textarea", default_required=True),
        # 解决方案只在工单建立后的编辑弹窗里出现 —— 新建工单时还谈不上解决方案
        _f("resolution", "解决方案", "textarea", available_on_create=False),
        # 处理人经「分配工单」专用弹窗设置，工单表单上没有该输入项
        _f("assigned_to_id", "处理人", "person",
           companions=("assigned_to_name",), form_editable=False),
        # 满意度由客户评价流程写入
        _f("satisfaction_score", "满意度评分", "number", form_editable=False),
        _f("satisfaction_comment", "满意度评价", "textarea", form_editable=False),
    ],
    # entity_type="payment" 在前后端实际只绑定 PaymentRecord（到账记录）——
    # payment_plans / invoices 没有 custom_fields_json 列，它们的金额改由按权限脱敏的
    # app/common/field_mask.py 覆盖（见 DEFAULT_MASK_POLICIES 与「字段脱敏」配置页）。
    "payment": [
        _f("received_date", "到账日期", "date", default_required=True),
        _f("amount", "到账金额", "amount", default_required=True),
        _f("channel", "到账渠道"),
        _f("reference_no", "凭证号"),
        # 新增弹窗的「备注」在 计划/到账/发票 三个分支共用同一个 Form.Item，
        # 套上到账记录的策略会连带影响另两类单据，故不接表单策略（读取侧照常脱敏）
        _f("remark", "备注", "textarea", form_editable=False),
    ],
    "order": [
        _f("title", "订单标题"),
        _f("amount", "订单金额", "amount", form_editable=False),  # 由明细行汇总，表单不直接填
        _f("currency", "币种"),
        _f("order_date", "订单日期", "date"),
        _f("delivery_date", "交付日期", "date"),
        _f("owner_id", "负责人", "person", companions=("owner_name",)),
        _f("remark", "备注", "textarea"),
    ],
    # 方案管理：独立业务实体（勿与图纸领用/安装图低代码表单混用）。
    # 表单尚未接 PolicyItem（不在 FORM_WIRED），目录供设计器只读展示与读取侧脱敏。
    "solution": [
        _f("solution_no", "方案编号", form_editable=False, available_on_create=False),
        _f("status", "状态", "select", form_editable=False, available_on_create=False,
           options=[{"value": "draft", "label": "草稿"},
                    {"value": "reviewing", "label": "评审中"},
                    {"value": "approved", "label": "已批准"},
                    {"value": "obsolete", "label": "已作废"}]),
        _f("assignee_id", "负责人", "person", companions=("assignee_name",)),
        _f("department_id", "部门", "department", companions=("department_name",)),
        _f("current_version_no", "当前版本号", "number", form_editable=False, available_on_create=False),
        _f("created_by_id", "创建人", "person", companions=("created_by_name",),
           form_editable=False, available_on_create=False),
    ],
    # 合同评审表单尚未接 PolicyItem（不在 FORM_WIRED），目录供设计器只读展示与读取侧脱敏。
    "contract_review": [
        _f("review_type", "合同评审/项目评审", "select",
           options=[{"value": "合同评审", "label": "合同评审"},
                    {"value": "项目评审", "label": "项目评审"}]),
        _f("is_export", "是否出口合同", "select", options=_YES_NO, default_required=True),
        _f("need_pricing", "是否核价", "select", default_required=True,
           options=[{"value": "有核价", "label": "有核价"}, {"value": "未核价", "label": "未核价"}]),
        _f("need_install", "是否需要安装", "select", default_required=True,
           options=[{"value": "指导安装", "label": "指导安装"},
                    {"value": "负责安装", "label": "负责安装"},
                    {"value": "无需指导安装", "label": "无需指导安装"}]),
        _f("owner_id", "业务员", "person", companions=("owner_name",), default_required=True),
        _f("region_manager_id", "区域经理/组长", "person",
           companions=("region_manager_name",)),
        _f("department_id", "业务部门", "department", companions=("department_name",)),
        _f("company_name", "公司名称", default_required=True),
        _f("elec_ctrl", "电控装置", "select", default_required=True,
           options=[{"value": v, "label": v} for v in (
               "含电控电缆", "含电控不含电缆", "不含电控不含电缆", "不含电控含电缆",
           )]),
        _f("customer_type", "客户类型", "select",
           options=[{"value": "新客户", "label": "新客户"}, {"value": "老客户", "label": "老客户"}]),
        _f("project_title", "项目名称及应用", "textarea"),
        _f("reported_at", "报备时间", "datetime", default_required=True),
        _f("contract_amount", "合同价格（元）", "amount"),
        _f("delivery_period", "交货期"),
        _f("payment_term", "账期", default_required=True),
        _f("conclusion", "结论描述", "textarea"),
    ],
}


# 内置显隐规则：表达业务上「某字段仅在特定条件下才适用」的事实，与租户自配规则同格式、
# 走同一个规则引擎，永远排在租户规则之前。
#
# 存在的理由：这类字段在表单 JSX 里本就是条件渲染的（如线索的「国家」只在国别=国外时才
# 出现）。若不把该条件告诉引擎，租户一旦给它勾上必填，国内线索就会被后端拦下、界面上却
# 根本找不到这个字段可填 —— 无法自救的死锁。把条件声明成规则，比在校验逻辑里为具体字段
# 加特例更干净：引擎已经会「跳过被隐藏字段的必填」，复用即可。
SYSTEM_RULES: dict[str, list[dict[str, Any]]] = {
    "lead": [
        {
            "id": "__sys_country_name_overseas_only",
            "type": "visibility",
            "target_field_id": "country_name",
            "condition": {"field": "country_type", "operator": "eq", "value": "overseas"},
            "action": {"visible": True},
        },
        {
            "id": "__sys_country_name_required",
            "type": "required",
            "target_field_id": "country_name",
            "condition": {"field": "country_type", "operator": "eq", "value": "overseas"},
            "action": {"required": True},
        },
        {
            "id": "__sys_conflict_note_when_yes",
            "type": "visibility",
            "target_field_id": "conflict_note",
            "condition": {"field": "has_internal_conflict", "operator": "eq", "value": "是"},
            "action": {"visible": True},
        },
        {
            "id": "__sys_conflict_note_required",
            "type": "required",
            "target_field_id": "conflict_note",
            "condition": {"field": "has_internal_conflict", "operator": "eq", "value": "是"},
            "action": {"required": True},
        },
        {
            "id": "__sys_bid_fail_reason_when_lost",
            "type": "visibility",
            "target_field_id": "bid_fail_reason",
            "condition": {
                "field": "bid_result",
                "operator": "in",
                "value": ["落标", "流标", "未参与"],
            },
            "action": {"visible": True},
        },
    ],
    # 合同登记显隐：对齐简道云 fieldShowRules（见 docs/product/_jdy_contract_reg_linkages.md）
    "contract": [
        {
            "id": "__sys_change_reason_when_change",
            "type": "visibility",
            "target_field_id": "change_reason",
            "condition": {"field": "change_type", "operator": "in", "value": ["change", "变动"]},
            "action": {"visible": True},
        },
        {
            "id": "__sys_change_reason_required",
            "type": "required",
            "target_field_id": "change_reason",
            "condition": {"field": "change_type", "operator": "in", "value": ["change", "变动"]},
            "action": {"required": True},
        },
        {
            "id": "__sys_missing_items_when_incomplete",
            "type": "visibility",
            "target_field_ids": ["missing_items", "info_incomplete_note"],
            "condition": {"field": "info_complete", "operator": "eq", "value": "否"},
            "action": {"visible": True},
        },
        {
            "id": "__sys_missing_items_required",
            "type": "required",
            "target_field_id": "missing_items",
            "condition": {"field": "info_complete", "operator": "eq", "value": "否"},
            "action": {"required": True},
        },
        {
            "id": "__sys_export_type_when_export",
            "type": "visibility",
            "target_field_id": "export_type",
            "condition": {"field": "is_export", "operator": "eq", "value": "是"},
            "action": {"visible": True},
        },
        {
            "id": "__sys_export_type_required",
            "type": "required",
            "target_field_id": "export_type",
            "condition": {"field": "is_export", "operator": "eq", "value": "是"},
            "action": {"required": True},
        },
        {
            "id": "__sys_delivery_mode_when_standard",
            "type": "visibility",
            "target_field_id": "delivery_mode",
            "condition": {"field": "standard_delivery", "operator": "eq", "value": "是"},
            "action": {"visible": True},
        },
        {
            "id": "__sys_delivery_mode_required",
            "type": "required",
            "target_field_id": "delivery_mode",
            "condition": {"field": "standard_delivery", "operator": "eq", "value": "是"},
            "action": {"required": True},
        },
        {
            "id": "__sys_fill_code_when_rotary",
            "type": "visibility",
            "target_field_id": "fill_code",
            "condition": {"field": "is_rotary_sieve", "operator": "eq", "value": "是"},
            "action": {"visible": True},
        },
        {
            "id": "__sys_smart_points_when_intel",
            "type": "visibility",
            "target_field_id": "smart_points",
            "condition": {"field": "has_intelligence", "operator": "eq", "value": "是"},
            "action": {"visible": True},
        },
        {
            "id": "__sys_smart_points_required",
            "type": "required",
            "target_field_id": "smart_points",
            "condition": {"field": "has_intelligence", "operator": "eq", "value": "是"},
            "action": {"required": True},
        },
    ],
    # 客户信息显隐：对齐简道云 fieldShowRules（条件成立 → visible:True；不成立则引擎取反隐藏）
    "customer": [
        {
            "id": "__sys_customer_smart_when_yes",
            "type": "visibility",
            "target_field_ids": [
                "legal_person", "headcount", "smart_industry_category",
                "annual_run_days", "floor_area", "financial_status", "business_status",
                "annual_power_usage", "daily_operate_hours",
            ],
            "condition": {"field": "is_smart_filing", "operator": "in", "value": [True, "是"]},
            "action": {"visible": True},
        },
        {
            "id": "__sys_customer_domestic_when_not_foreign",
            "type": "visibility",
            "target_field_ids": [
                "registered_capital", "paid_in_capital", "founded_year", "parent_company_note",
                "customer_nature", "customer_relation", "level", "primary_contact_title",
                "wage_insurance_status",
                "taxpayer_id", "invoice_address_phone", "bank_account", "is_company_customer",
            ],
            "condition": {"field": "is_foreign_trade", "operator": "in", "value": [False, "否"]},
            "action": {"visible": True},
        },
        {
            "id": "__sys_customer_foreign_when_yes",
            "type": "visibility",
            "target_field_ids": [
                "country", "short_name", "foreign_customer_code", "foreign_customer_type",
                "focus_product", "customer_email", "main_products_json",
                "website", "source", "region",
            ],
            "condition": {"field": "is_foreign_trade", "operator": "in", "value": [True, "是"]},
            "action": {"visible": True},
        },
        # 外贸区标签带 *（客户简称*/国别*/客户类型*/邮箱*）：外贸=是时必填
        {
            "id": "__sys_customer_foreign_star_required",
            "type": "required",
            "target_field_ids": ["short_name", "country", "foreign_customer_type", "customer_email"],
            "condition": {"field": "is_foreign_trade", "operator": "in", "value": [True, "是"]},
            "action": {"required": True},
        },
    ],
}


def get_system_rules(entity_type: str) -> list[dict[str, Any]]:
    import copy
    return copy.deepcopy(SYSTEM_RULES.get(entity_type) or [])


_SYS_RULE_OVERRIDE_KEYS = (
    "type", "target_field_id", "target_field_ids", "condition", "action", "enabled",
)


def merge_system_rules(
    entity_type: str, stored_rules: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """目录默认系统规则 ← 租户 `__sys_*` 覆盖，再拼上非系统租户规则。

    新产品加进 SYSTEM_RULES 的条目会自动出现；已落库的同 id 覆盖仍优先生效。
    `enabled: false` 表示停用该条系统规则（仍保留在列表里供设计器展示）。
    """
    import copy
    defaults = get_system_rules(entity_type)
    stored = [r for r in (stored_rules or []) if isinstance(r, dict)]
    overrides = {
        str(r.get("id")): r
        for r in stored
        if str(r.get("id") or "").startswith("__sys_")
    }
    merged_sys: list[dict[str, Any]] = []
    for d in defaults:
        rid = str(d.get("id") or "")
        ov = overrides.get(rid)
        if not ov:
            merged_sys.append(d)
            continue
        item = copy.deepcopy(d)
        for key in _SYS_RULE_OVERRIDE_KEYS:
            if key in ov:
                item[key] = copy.deepcopy(ov[key])
        merged_sys.append(item)
    tenant = [r for r in stored if not str(r.get("id") or "").startswith("__sys_")]
    return merged_sys + tenant


def get_native_fields(entity_type: str) -> list[dict[str, Any]]:
    """该实体的原生字段目录（深拷贝，调用方可安全改写）。"""
    import copy
    return copy.deepcopy(CATALOG.get(entity_type) or [])


def has_native_catalog(entity_type: str) -> bool:
    return bool(CATALOG.get(entity_type))


def merge_native_overrides(
    entity_type: str, stored: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """用租户存下的覆盖项重建原生字段定义。

    stored 里 native=True 的条目按 id 匹配目录项，仅允许覆盖 OVERRIDABLE_KEYS；
    目录里没有的陈旧条目直接忽略（代码删掉某原生字段后不会残留脏配置）。
    """
    overrides = {
        fd.get("id"): fd for fd in (stored or [])
        if isinstance(fd, dict) and fd.get("native") and fd.get("id")
    }
    out: list[dict[str, Any]] = []
    for base in get_native_fields(entity_type):
        ov = overrides.get(base["id"])
        # 目录规定创建不可用时，禁止租户改回创建可见（避免新建又被要求填「中标情况」等）
        catalog_create_ok = base.get("available_on_create", True) is not False
        if ov:
            for key in OVERRIDABLE_KEYS:
                if key not in ov:
                    continue
                if key == "available_on_create" and not catalog_create_ok:
                    continue
                if key == "props":
                    props = {k: v for k, v in (ov.get("props") or {}).items()
                             if k in OVERRIDABLE_PROP_KEYS}
                    base["props"] = {**(base.get("props") or {}), **props}
                else:
                    base[key] = ov[key]
            # 单独标出「租户确实改过标签」。base["label"] 始终有值(目录默认名)，业务表单
            # 若据此覆盖自己的 JSX 标签，会在租户什么都没配的情况下把
            # 「日期」改成「业务日期」这类既有文案 —— 故只有真正的覆盖才透出。
            if isinstance(ov.get("label_override"), str) and str(ov["label_override"]).strip():
                base["label_override"] = str(ov["label_override"]).strip()
            elif isinstance(ov.get("label"), str) and ov["label"].strip():
                base["label_override"] = ov["label"].strip()
        # 系统必填不可被降级为非必填
        if base.get("system_required"):
            base["required"] = True
        out.append(base)
    return out
