#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate CRM builtin「迅焊公司合同评审」from JDY dumps.

Sources:
  docs/product/_jdy_xunhan_contract_review_{fields,workflows_raw,edit_raw}.json
Output:
  backend/app/domains/lowcode/_xunhan_contract_review_generated.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _gen_drawing_jdy import (  # noqa: E402
    apply_pickable_scope,
    build_flow,
    build_rule_definitions,
    label_of,
    load_widget_limits_from_edit_raw,
    map_type,
    options_of,
)

OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
GEN = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "domains"
    / "lowcode"
    / "_xunhan_contract_review_generated.py"
)

SOFT_NOISE_KEYS = (
    "辅助", "已取消", "打印模板", "筛选用", "公式的", "主键", "离职",
    "取消", "停用", "不用显示",
)
HARD_DROP_KEYS = ("22/11/30取消", "23.11.25取消", "230522取消", "260518取消")
HARD_DROP_LABELS = frozenset({
    "是否销售小萌（23.11.25取消）",
    "室主任（230522取消，但流程版本V26用到）",
    "核价时间（22/11/30取消）",
})
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}

TITLE_SLUG = {
    "流水号": "serial_no",
    "是否核价": "has_pricing",
    "是否需要安装": "need_install",
    "业务员": "sales_person",
    "业务部门": "department",
    "选择公司名称": "customer_name",
    "公司名称": "customer_name_text",
    "是否外贸客户": "is_foreign_trade",
    "是否小萌": "is_xiaomeng",
    "电控装置": "elec_control",
    "选择27.7核价管理信息": "pricing_pick",
    "核价单号": "pricing_no",
    "成本附件250122": "cost_attachments",
    "成本价250122": "cost_price",
    "核价配置要求的电机": "pricing_motor",
    "核价配置要求的轴承": "pricing_bearing",
    "核价配置要求的主材材质": "pricing_material",
    "核价配置要求的衬板/筛板": "pricing_liner",
    "特殊要求": "special_req",
    "客户类型": "customer_type",
    "正式合同份数": "contract_copies",
    "公司性质*": "company_nature",
    "公司性质": "company_nature",
    "所属行业*": "industry",
    "所属行业": "industry",
    "规模及资金（万元）*": "scale_fund",
    "规模及资金（万元）": "scale_fund",
    "客户关系*": "customer_relation",
    "客户关系": "customer_relation",
    "失信信息": "dishonesty_count",
    "诉讼纠纷": "lawsuit_count",
    "环保处罚": "env_penalty_count",
    "税务处罚": "tax_penalty_count",
    "其它行政处罚": "other_penalty_count",
    "联系信息": "contacts",
    "联系人": "contact_name",
    "上级领导": "contact_leader",
    "手机号码": "contact_mobile",
    "职务": "contact_title",
    "邮箱or请示": "email_or_request",
    "邮箱": "contact_email",
    "请示": "contact_request",
    "地址": "contact_address",
    "母公司或控股公司的情况及性质说明*": "parent_company_desc",
    "母公司或控股公司的情况及性质说明": "parent_company_desc",
    "项目名称及应用": "project_name_app",
    "工资及保险情况*": "salary_insurance",
    "工资及保险情况": "salary_insurance",
    "合同价格（元）": "contract_price",
    "交货期": "delivery_period",
    "是否有保函": "has_guarantee",
    "保函类型": "guarantee_type",
    "是否有重量要求": "has_weight_req",
    "是否趁用呆滞设备": "use_idle_equipment",
    "合同是否含智能化部分": "has_smart_part",
    "合同签订依据及情况": "sign_basis",
    "参考合同号": "ref_contract_no",
    "付款方式": "payment_method",
    "公司现状调查": "company_survey",
    "项目报备与投标情况": "bid_status",
    "针对销售情况的补充": "sales_supplement",
    "现场测绘及要求": "survey_req",
    "附件": "attachments",
    "图片": "images",
    "合同条款审核意见": "legal_clause_opinion",
    "法务风险等级判断": "legal_risk_level",
    "法务风险等级文字描述": "legal_risk_desc",
    "技术风险等级判断": "tech_risk_level",
    "技术风险等级文字描述": "tech_risk_desc",
    "业务风险等级判断": "biz_risk_level",
    "业务风险等级文字描述": "biz_risk_desc",
    "财务风险等级判断": "finance_risk_level",
    "财务风险等级文字描述": "finance_risk_desc",
    "采购风险等级判断": "purchase_risk_level",
    "采购风险等级文字描述": "purchase_risk_desc",
    "出口风险等级判断": "export_risk_level",
    "出口风险等级文字描述": "export_risk_desc",
    "重点数据及信用等级": "credit_level",
    "前期业务来往描述": "history_biz_desc",
    "核价报价补充": "pricing_quote_supplement",
    "账期": "payment_term",
    "结论描述": "conclusion_desc",
    "是否反馈": "need_feedback",
    "成员多选": "feedback_members",
    "反馈附件": "feedback_attachments",
    "反馈图片": "feedback_images",
    "图纸编号": "drawing_no",
    "合同评审意见执行情况": "review_opinion_exec",
}

FORM = {
    "key": "xunhan_contract_review",
    "title": "迅焊公司合同评审",
    "entry": "67d3d515c8df85cc24de064f",
    "route": "/xunhan-contract-reviews",
    "fields_file": "_jdy_xunhan_contract_review_fields.json",
    "wf_file": "_jdy_xunhan_contract_review_workflows_raw.json",
    "edit_file": "_jdy_xunhan_contract_review_edit_raw.json",
    "md_file": "_jdy_xunhan_contract_review_crm_forms.md",
}

# 审批阶段填写（风险/反馈/结论等）
_APPROVER_FILL = frozenset({
    "legal_clause_opinion",
    "legal_risk_level", "legal_risk_desc",
    "tech_risk_level", "tech_risk_desc",
    "biz_risk_level", "biz_risk_desc",
    "finance_risk_level", "finance_risk_desc",
    "purchase_risk_level", "purchase_risk_desc",
    "export_risk_level", "export_risk_desc",
    "credit_level", "history_biz_desc", "pricing_quote_supplement",
    "payment_term", "conclusion_desc", "need_feedback",
    "feedback_members", "feedback_attachments", "feedback_images",
    "drawing_no", "review_opinion_exec",
    "cost_attachments", "cost_price",
})

_CREATE_REQUIRED = frozenset({
    "has_pricing",
    "need_install",
    "sales_person",
    "department",
    "customer_name",
    "customer_type",
    "contract_price",
    "has_guarantee",
})


def _norm_label(label: str) -> str:
    return (label or "").replace("*", "").strip()


def is_hard_drop(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = _norm_label(label)
    if not lab or lab.startswith("_"):
        return True
    if lab in HARD_DROP_LABELS or (label or "").strip() in HARD_DROP_LABELS:
        return True
    return any(k in (label or "") for k in HARD_DROP_KEYS)


def is_soft_noise(label: str) -> bool:
    lab = label or ""
    return any(k in lab for k in SOFT_NOISE_KEYS)


def should_keep_field(label: str, name: str) -> bool:
    if is_hard_drop(label, name):
        return False
    if is_soft_noise(label):
        return False
    return True


def _slug_for(label: str, used: set[str]) -> str:
    lab = _norm_label(label)
    base = TITLE_SLUG.get(label) or TITLE_SLUG.get(lab)
    if not base:
        base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", lab).strip("_").lower()
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", base).strip("_").lower() or "field"
        if base[0].isdigit():
            base = "f_" + base
    slug = base
    i = 2
    while slug in used:
        slug = f"{base}_{i}"
        i += 1
    used.add(slug)
    return slug


def sub_columns(f: dict, used: set[str]) -> list[dict]:
    cols = f.get("widgets") or []
    if not cols:
        cols = [
            x for x in (f.get("items") or [])
            if isinstance(x, dict) and x.get("type") and x.get("type") not in SKIP_TYPES
        ]
    out = []
    for c in cols:
        lab = label_of(c) or c.get("name") or "col"
        name = c.get("name") or ""
        if not should_keep_field(lab, name):
            continue
        typ0 = (c.get("type") or "").lower()
        if typ0 in SKIP_TYPES:
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        opts = options_of(c)
        if typ == "select" and not opts:
            typ = "text"
        fd = {"id": _slug_for(lab, used), "type": typ, "label": _norm_label(lab) or lab}
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def build_fields(raw: dict, widget_limits: dict[str, dict] | None = None) -> list[dict]:
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out = []
    limits = widget_limits or {}
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f)
        name = f.get("name") or ""
        if typ0 in SKIP_TYPES:
            continue
        if not lab or not should_keep_field(lab, name):
            continue
        slug = _slug_for(lab, used)
        display = _norm_label(lab) or lab
        if slug == "serial_no" or display == "流水号":
            fd = {
                "id": "serial_no",
                "type": "auto_number",
                "label": "流水号",
                "props": {
                    "serial_rules": [
                        {"type": "text", "value": "24.2.3"},
                        {"type": "date", "format": "yyyyMMdd"},
                        {
                            "type": "counter",
                            "digits": 5,
                            "fixed": True,
                            "reset_period": "monthly",
                            "initial_value": 1,
                        },
                    ],
                },
                "available_on_create": True,
                "fill_stage": "initiator",
                "form_editable": False,
            }
            if name:
                fd["jdy_widget"] = name
            out.append(fd)
            continue
        typ = map_type(typ0)
        if typ0 in ("linkfield", "combo") and display in ("选择公司名称", "公司名称"):
            typ = "customer"
            slug = "customer_name"
            used.discard(_slug_for(lab, set()))  # no-op safety
            if "customer_name" not in used:
                used.add("customer_name")
            display = "公司名称"
        if typ0 == "linkfield" and typ != "customer":
            typ = "text"
        if typ0 == "combo" and display == "图纸编号":
            typ = "text"
        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"
        fd: dict = {"id": slug, "type": typ, "label": display}
        if typ == "customer":
            fd["description"] = "从客户管理中选择。"
        if slug in _CREATE_REQUIRED:
            fd["required"] = True
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
        elif slug in _APPROVER_FILL:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
        else:
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")
        if slug == "sales_person":
            fd.setdefault("props", {})["default_current_user"] = True
        if slug == "department":
            fd.setdefault("props", {})["default_current_dept"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used)
            if cols:
                fd["detail_table_columns"] = cols
            else:
                continue
        if name:
            fd["jdy_widget"] = name
        if typ in ("person", "person_multi"):
            apply_pickable_scope(fd, limit=limits.get(name), jdy_field=f)
        out.append(fd)
    # 去重：若同时有 customer_name 与 customer_name_text，保留选择器
    by_id = {}
    for fd in out:
        by_id[fd["id"]] = fd
    if "customer_name" in by_id and "customer_name_text" in by_id:
        by_id.pop("customer_name_text", None)
    return list(by_id.values())


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def load_linkage() -> dict:
    path = OUT / FORM["edit_file"]
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    content = raw.get("data") or raw.get("content") or raw
    attr = content.get("attr") or {}
    link = attr.get("linkage") or content.get("linkage") or {}
    fsr = link.get("fieldShowRules") or content.get("fieldShowRules") or []
    ssr = link.get("subformFieldShowRules") or content.get("subformFieldShowRules") or []
    # 部分表单 subformFieldShowRules 仅为子表 widget id 字符串，跳过
    fsr = [r for r in fsr if isinstance(r, dict)]
    ssr = [r for r in ssr if isinstance(r, dict)]
    return {"fieldShowRules": fsr, "subformFieldShowRules": ssr}


def gen_one() -> dict:
    fields_raw = json.loads((OUT / FORM["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / FORM["wf_file"]).read_text(encoding="utf-8")))
    widget_limits = {}
    edit_path = OUT / FORM["edit_file"]
    if edit_path.exists():
        widget_limits = load_widget_limits_from_edit_raw(edit_path)
    fields = build_fields(fields_raw, widget_limits)
    linkage = load_linkage()
    rules = build_rule_definitions(linkage, fields)
    vis_n = sum(1 for r in rules if r.get("type") == "visibility")
    nodes, routes, notes = build_flow(wf_raw, fields, FORM["title"])
    notes.insert(0, "对齐简道云销售中心「迅焊公司合同评审」；流水号 24.2.3+yyyyMMdd+五位月序。")
    notes.insert(
        1,
        f"简道云 fieldShowRules {len(linkage.get('fieldShowRules') or [])} 条 → CRM 显隐 {vis_n} 条。",
    )

    pack = {
        "name": FORM["title"],
        "field_definitions": fields,
        "rule_definitions": rules,
        "flow_nodes": nodes,
        "flow_routes": routes,
        "notes": notes,
    }

    n_req = sum(1 for f in fields if f.get("required"))
    md = [
        f"# {FORM['title']} — CRM 字段对照",
        "",
        f"> 简道云 app=`5de0b3e85600ec0006f420f2` entry=`{FORM['entry']}`（销售中心 / 合同）",
        "",
        f"- **builtin key**: `{FORM['key']}`",
        f"- **路由**: `{FORM['route']}`",
        f"- **字段数（去噪后）**: {len(fields)}",
        f"- **静态必填**: {n_req}",
        f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
        f"- **联动规则**: {len(rules)}",
        f"- **流水号**: `24.2.3` + yyyyMMdd + 五位月序",
        "",
        "| slug | 标签 | type | 必填 | jdy_widget |",
        "|------|------|------|------|------------|",
    ]
    for fd in fields:
        md.append(
            f"| {fd['id']} | {fd['label']} | {fd['type']} | "
            f"{'是' if fd.get('required') else ''} | `{fd.get('jdy_widget', '')}` |"
        )
        for col in fd.get("detail_table_columns") or []:
            md.append(
                f"| └ {col['id']} | {col['label']} | {col['type']} | "
                f"{'是' if col.get('required') else ''} | `{col.get('jdy_widget', '')}` |"
            )
    md += ["", "### 流程降级备注", ""]
    for n in notes:
        md.append(f"- {n}")
    md.append("")
    (OUT / FORM["md_file"]).write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        f"{FORM['key']}: fields={len(fields)} required={n_req} "
        f"nodes={len(nodes)} routes={len(routes)} rules={len(rules)}"
    )
    return {FORM["key"]: pack}


def main() -> None:
    result = gen_one()
    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
        "\"\"\"Auto-generated from docs/product/_jdy_xunhan_contract_review_* dumps. "
        "Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"XUNHAN_CONTRACT_REVIEW_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
