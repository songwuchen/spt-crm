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
}
# props 里允许覆盖的子键（其余 props 由目录决定，避免租户塞进影响渲染的任意配置）
OVERRIDABLE_PROP_KEYS = {"hidden", "readonly"}


def _f(fid: str, label: str, ftype: str = "text", *, system_required: bool = False,
       default_required: bool = False, options_source: str | None = None,
       companions: tuple[str, ...] = (), form_editable: bool = True,
       **props: Any) -> dict[str, Any]:
    """声明一个原生字段。

    system_required: 数据库 NOT NULL 或业务强依赖，恒为必填且租户不可改。
    default_required: 出厂默认必填，但租户可以改成非必填（用于保留改造前表单里硬编码的必填项）。
    options_source: 指向数据字典 dict_type 或内置枚举，供设计器展示可选值。
    companions: 该字段的「派生显示键」，出参里由它衍生但本身不是列的字段
        （如 owner_id 的 owner_name、department_id 的 department_name）。
        隐藏/脱敏必须连带处理它们 —— 列表页渲染的往往正是这些派生键，只裁主字段
        等于配了脱敏却毫无效果。
    form_editable: 该字段在业务表单上是否可填。False 表示由系统/专用流程写入
        （如合同签约日期走签署流程），此时：
          · 仍可配隐藏/脱敏 —— 它照样出现在列表与详情里，敏感性不因不可编辑而降低；
          · 不参与必填校验 —— 用户根本没有填它的入口，配必填只会造成无法保存；
          · 不参与「目录↔表单对齐」守卫测试。
    """
    fd: dict[str, Any] = {
        "id": fid, "label": label, "type": ftype,
        "native": True,               # 标记：前端据此禁用删除/改类型
        "system_required": system_required,
        "required": system_required or default_required,
        "form_editable": form_editable,
    }
    if companions:
        fd["companions"] = list(companions)
    if options_source:
        fd["options_source"] = options_source
    if props:
        fd["props"] = props
    return fd


# 已把表单接入 PolicyItem 的实体。只有这些实体的 required/条件显隐会在表单上生效；
# 其余实体目前只享用读取路径的隐藏/脱敏（列表、详情、导出）。
# 接入某实体表单后，把它加进来，test_catalog_fields_all_have_a_form_control 会开始校验对齐。
FORM_WIRED: set[str] = {"lead", "customer", "contact", "project", "contract", "order"}


# entity_type -> 该实体表单上可配置的原生字段（顺序即设计器/表单默认顺序）
CATALOG: dict[str, list[dict[str, Any]]] = {
    "lead": [
        # ---- 基本信息 ----
        _f("title", "线索标题", system_required=True),           # leads.title NOT NULL
        # 列可空，但改造前表单硬编码必填 —— 保留默认必填以免行为回退，租户可自行关掉
        _f("company_name", "公司名称", default_required=True),
        _f("customer_type", "客户类型", "select", options_source="dict:customer_type"),
        _f("industry", "行业", "select", options_source="dict:industry"),
        _f("source", "线索来源", "select", options_source="dict:lead_source"),
        _f("category", "类别", "select", options_source="enum:lead_category"),
        _f("department_id", "部门", "department", companions=("department_name",)),
        _f("budget_range", "预算范围", "select", options_source="dict:budget_range"),
        _f("owner_id", "负责人", "person", companions=("owner_name",)),
        _f("biz_date", "业务日期", "date"),
        # ---- 项目地址 ----
        _f("country_type", "国别", "select", options_source="enum:lead_country_type"),
        _f("country_name", "国家"),
        # province/city/district 刻意不入目录：它们由 RegionCascader 作为一个整体选择，
        # 表单里只有隐藏桩、没有独立可编辑项。若单独配必填，会出现「后端拦下、界面上却
        # 找不到该字段」的情况。省市区整体必填需要绑定级联控件，属于后续能力。
        _f("region", "详细地址"),
        # ---- 联系人 ----
        _f("contact_name", "联系人"),
        _f("contact_phone", "联系电话"),
        _f("contact_email", "联系邮箱"),
        # ---- 补充 ----
        _f("demand_summary", "需求摘要", "textarea"),
        _f("remark", "备注", "textarea"),
    ],

    # 以下实体的表单尚未接 PolicyItem（不在 FORM_WIRED 里），目录先服务于读取路径的
    # 隐藏/脱敏。字段以「敏感、值得按角色控制」为选取标准，全部核对过真实列名 ——
    # 被删掉的旧 field_rules UI 里 18 个字段有 12 个是不存在的列（如 customer.phone、
    # contract.amount），照那份清单配规则本就匹配不到任何东西。
    "customer": [
        _f("name", "客户名称", system_required=True),
        _f("address", "详细地址"),
        _f("website", "网址"),
        _f("budget_amount", "预算金额", "amount"),
        _f("demand", "需求描述", "textarea"),
        _f("expected_purchase_date", "预计采购日期", "date"),
        _f("headcount", "人数规模", "number"),
        _f("postal_code", "邮编"),
        _f("remark", "备注", "textarea"),
    ],
    "contact": [
        _f("name", "姓名", system_required=True),
        _f("title", "职务"),
        _f("phone", "电话"),
        _f("mobile", "手机"),
        _f("email", "邮箱"),
        _f("remark", "备注", "textarea"),
    ],
    "project": [
        _f("name", "商机名称", system_required=True),
        _f("amount_expect", "预期金额", "amount"),
        _f("probability", "赢单概率", "number"),
        _f("close_date_expect", "预计成交日期", "date"),
        _f("payment_method", "付款方式"),
        _f("remark", "备注", "textarea"),
    ],
    "contract": [
        # 注意是 amount_total 而非旧 UI 写的 amount
        _f("amount_total", "合同金额", "amount"),
        # 签约日期由签署流程写入，表单上没有该输入项 —— 可配脱敏，但不可配必填
        _f("signed_date", "签订日期", "date", form_editable=False),
        _f("end_date", "到期日期", "date"),
    ],
    # 报价的敏感字段(margin_rate/discount_total/cost_est)在 quote_versions / quote_lines /
    # cost_snapshots 上，不在 quotes 主表，本目录够不着 —— 那部分继续由按权限脱敏的
    # app/common/field_mask.py 负责（它本就是为这类嵌套响应体设计的）。
    "quote": [
        _f("quote_no", "报价单号", form_editable=False),  # 自动生成，表单上无输入项
    ],
    # 工单/回款的表单目前不是 antd Form（裸受控组件），未接 PolicyItem，故这两个实体
    # 的字段一律标为 form_editable=False：只享用读取路径的隐藏/脱敏与导出裁剪，
    # 不参与必填校验（配了也没有输入项可填）。表单改造后再逐个放开。
    "service_ticket": [
        _f("description", "问题描述", "textarea", form_editable=False),
        _f("resolution", "解决方案", "textarea", form_editable=False),
        _f("assigned_to_id", "处理人", "person",
           companions=("assigned_to_name",), form_editable=False),
        _f("satisfaction_score", "满意度评分", "number", form_editable=False),
        _f("satisfaction_comment", "满意度评价", "textarea", form_editable=False),
    ],
    # entity_type="payment" 在前后端实际只绑定 PaymentRecord（到账记录）——
    # payment_plans / invoices 没有 custom_fields_json 列，也不走这套。
    "payment": [
        _f("amount", "到账金额", "amount", form_editable=False),
        _f("channel", "到账渠道", form_editable=False),
        _f("reference_no", "凭证号", form_editable=False),
        _f("received_date", "到账日期", "date", form_editable=False),
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
    ],
}


def get_system_rules(entity_type: str) -> list[dict[str, Any]]:
    import copy
    return copy.deepcopy(SYSTEM_RULES.get(entity_type) or [])


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
        if ov:
            for key in OVERRIDABLE_KEYS:
                if key not in ov:
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
            if isinstance(ov.get("label"), str) and ov["label"].strip():
                base["label_override"] = ov["label"]
        # 系统必填不可被降级为非必填
        if base.get("system_required"):
            base["required"] = True
        out.append(base)
    return out
