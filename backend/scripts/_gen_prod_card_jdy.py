"""Generate CRM builtin fields + flow from pulled JDY prod_card dumps.

Sources:
  docs/product/_jdy_prod_card_fields.json
  docs/product/_jdy_prod_card_workflows_raw.json
  docs/product/_jdy_prod_card_linkages.json (allowBlank / fieldShowRules)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# reuse flow / rule builders from drawing generator
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gen_drawing_jdy import (  # noqa: E402
    build_flow,
    build_rule_definitions,
    label_of,
    map_type,
    options_of,
)

OUT = Path(r"g:\ruolin-a\spt-crm\docs\product")
GEN = Path(r"g:\ruolin-a\spt-crm\backend\app\domains\lowcode\_prod_card_jdy_generated.py")
LINKAGES = OUT / "_jdy_prod_card_linkages.json"

KEY = "prod_card_supplement"
TITLE = "生产卡/补充流程"

SOFT_NOISE_KEYS = (
    "辅助", "已取消", "打印模板", "筛选用", "公式的", "主键", "离职",
    "240503", "251128", "260518", "0414",
    "count辅助", "同一天", "补位", "有内容不清空",
)
HARD_DROP_KEYS = ("取消", "停用", "不用显示", "22/11/28", "230320")
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate", "sn",
    "aggregation", "linkquery", "formula",
}

TITLE_SLUG = {
    "下卡日期": "card_date",
    "所在部门": "department",
    "提交人": "submitter",
    "是否为补充": "is_supplement",
    "是否涉及外购": "involve_outsource",
    "是否只是财务的补充": "is_finance_only",
    "是否已发货": "is_shipped",
    "是否涉及金额变更": "involve_amount_change",
    "是否单位变更": "is_unit_change",
    "是否是机器人": "is_robot",
    "是否增加成本": "increase_cost",
    "是否需研究院部门出图": "need_research_drawing",
    "产品类型": "product_type",
    "是否为交钥匙工程": "is_turnkey",
    "责任方": "responsible_party",
    "图纸编号查询1": "drawing_no_query",
    "（否）业务人员": "no_sales_person",
    "（否）图纸编号（图纸编号查询填充）": "no_drawing_no",
    "合同号选择1": "contract_no_select",
    "油漆要求（补充）": "paint_req_supplement",
    "（是）合同号": "yes_contract_no",
    "（是）业务人员": "yes_sales_person",
    "（是）单位名称": "yes_customer_name",
    "客户及业务员选择": "customer_sales_select",
    "说明": "description",
    "区域经理/组长": "region_manager",
    "标准化室填写": "std_room_fill",
    "电气车间填写": "elec_workshop_fill",
    "是否需要公司派人": "need_dispatch",
    "是否需要转电气车间": "need_elec_workshop",
    "是否有技术协议": "has_tech_agreement",
    "技术协议是否企标模板": "tech_agreement_std",
    "附件": "attachments",
    "图片": "images",
    "请确认是否同意按本协议约定、方案执行": "confirm_agreement",
    "设计单分派": "design_dispatch",
    "转新乡、工艺包装": "transfer_packaging_users",
    "设计指派": "design_assignees",
    "科室": "offices",
    "下单时间": "order_datetime",
    "下单类型": "order_type",
    "是否有对应安装图项目号": "has_install_project",
    "安装图项目号": "install_project_no",
    "合同明细（生产卡）": "prod_card_line_items",
    "包装要求（生产卡）": "packaging_req",
    "项目名称（生产卡）": "project_name",
    "油漆要求（生产卡）": "paint_req",
    "技术参数及要求（生产卡）": "tech_params",
    "（否）质保期限": "no_warranty_period",
    "特别提醒（生产卡）": "special_reminder",
    "备注（生产卡）": "remark_prod_card",
    "特别提醒（生产卡）多": "special_reminder_multi",
    "是否有合同技术协议评审": "has_contract_tech_review",
    "选择合同技术协议评审": "select_contract_tech_review",
    "合同技术协议评审流水号": "contract_tech_review_sn",
    # subform columns
    "对应的合同明细": "contract_line_ref",
    "物料代码": "material_code",
    "产品名称": "product_name",
    "规格型号": "spec_model",
    "单位": "unit",
    "数量": "qty",
    "理论重量": "theoretical_weight",
    "BOM内容备注": "bom_remark",
    "填写物料代码时间": "material_code_time",
    "设计人": "designer",
    "备注": "remark",
    "电控装置": "electric_control",
    "技术参数及要求": "tech_params_line",
}


def is_hard_drop(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = label or ""
    if not lab or lab.startswith("_"):
        return True
    return any(k in lab for k in HARD_DROP_KEYS)


def is_soft_noise(label: str) -> bool:
    return any(k in (label or "") for k in SOFT_NOISE_KEYS)


def should_keep_field(
    label: str, name: str, required_widgets: set[str], rule_widgets: set[str],
) -> bool:
    if is_hard_drop(label, name):
        return False
    if name in required_widgets or name in rule_widgets:
        return True
    if is_soft_noise(label):
        return False
    return True


def _slug_for(label: str, used: set[str]) -> str:
    base = TITLE_SLUG.get(label)
    if not base:
        base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", label).strip("_").lower()
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


def load_linkage_pack() -> dict:
    if not LINKAGES.exists():
        return {}
    raw = json.loads(LINKAGES.read_text(encoding="utf-8"))
    return normalize_linkage_pack(raw)


def normalize_linkage_pack(pack: dict) -> dict:
    """JDY edit raw uses filter/fields; drawing generator expects conditions/show_fields."""
    out = dict(pack)
    normalized: list[dict] = []
    for rule in pack.get("fieldShowRules") or []:
        if rule.get("conditions") and rule.get("show_fields"):
            normalized.append(rule)
            continue
        filt = rule.get("filter") or {}
        conds = []
        for c in filt.get("cond") or []:
            if not isinstance(c, dict):
                continue
            wid = c.get("field") or c.get("trigger_widget")
            if not wid:
                continue
            conds.append({
                "trigger_widget": wid,
                "method": c.get("method") or "eq",
                "value": c.get("value"),
            })
        show_fields = [{"widget": w} for w in (rule.get("fields") or []) if w]
        if conds and show_fields:
            normalized.append({
                "rel": filt.get("rel") or "and",
                "conditions": conds,
                "show_fields": show_fields,
            })
    out["fieldShowRules"] = normalized
    return out


def collect_linkage_sets(pack: dict) -> tuple[set[str], set[str], set[str]]:
    required: set[str] = set()
    for r in pack.get("required_fields") or []:
        if isinstance(r, dict) and r.get("widget"):
            required.add(r["widget"])
    rule_widgets: set[str] = set()
    for rule in pack.get("fieldShowRules") or []:
        for c in rule.get("conditions") or []:
            if c.get("trigger_widget"):
                rule_widgets.add(c["trigger_widget"])
            if c.get("field"):
                rule_widgets.add(c["field"])
        filt = rule.get("filter") or {}
        for c in filt.get("cond") or []:
            if isinstance(c, dict) and c.get("field"):
                rule_widgets.add(c["field"])
        for sf in rule.get("show_fields") or []:
            if sf.get("widget"):
                rule_widgets.add(sf["widget"])
        for wid in rule.get("fields") or []:
            if wid:
                rule_widgets.add(wid)
    for rule in pack.get("subformFieldShowRules") or []:
        if rule.get("subform_widget"):
            rule_widgets.add(rule["subform_widget"])
        for c in rule.get("conditions") or []:
            if c.get("trigger_widget"):
                rule_widgets.add(c["trigger_widget"])
        for sf in rule.get("show_fields") or []:
            if sf.get("widget"):
                rule_widgets.add(sf["widget"])
    return required, rule_widgets, required


def sub_columns(
    f: dict, used: set[str], required_widgets: set[str], rule_widgets: set[str],
) -> list[dict]:
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
        if not should_keep_field(lab, name, required_widgets, rule_widgets):
            continue
        typ0 = (c.get("type") or "").lower()
        if typ0 in SKIP_TYPES:
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        if typ == "detail_table":
            continue
        fd = {"id": _slug_for(lab, used), "type": typ, "label": lab}
        if name in required_widgets:
            fd["required"] = True
        opts = options_of(c)
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def build_fields(raw: dict, required_widgets: set[str], rule_widgets: set[str]) -> list[dict]:
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f)
        name = f.get("name") or ""
        if typ0 in SKIP_TYPES:
            continue
        if not lab or not should_keep_field(lab, name, required_widgets, rule_widgets):
            continue
        slug = _slug_for(lab, used)
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        fd: dict = {"id": slug, "type": typ, "label": lab}
        if name in required_widgets or f.get("required"):
            fd["required"] = True
        opts = options_of(f)
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used, required_widgets, rule_widgets)
            if cols:
                fd["detail_table_columns"] = cols
            else:
                continue
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def _cond_summary(cond: dict) -> str:
    if not cond:
        return ""
    if "cond" in cond and isinstance(cond.get("cond"), list):
        parts = [
            _cond_summary(c) if isinstance(c, dict) and "cond" in c
            else f"{c.get('field')} {c.get('operator')} {c.get('value')!r}"
            for c in cond["cond"] if isinstance(c, dict)
        ]
        return f"({(cond.get('rel') or 'and').upper()} " + "; ".join(parts) + ")"
    return f"{cond.get('field')} {cond.get('operator')} {cond.get('value')!r}"


def patch_sales_confirm_node(
    nodes: list[dict], routes: list[dict], notes: list[str],
) -> tuple[list[dict], list[dict], list[str]]:
    """补齐简道云画布 V43 的「业务员确认」，并校正区域经理串行。

    线上画布（V43）正确拓扑：
      生产卡发起 --else--> 业务员确认
      业务员确认 --区域经理不为空--> 区域经理/组长 --> 部门审批
      业务员确认 --else--> 部门审批

    data-hub ``workflow_config`` 缓存（约 2026-07-01）无「业务员确认」，且把
    「区域不为空」挂在发起上；补节点后须把该边挪到业务员确认之后。
    """
    from app.domains.lowcode.prod_card_contract_fill import (
        apply_prod_card_sales_before_region,
    )

    if not any(n.get("name") == "业务员确认" for n in nodes):
        dept = next((n for n in nodes if n.get("name") == "部门审批"), None)
        if not dept:
            notes.append("无法补齐「业务员确认」：未找到部门审批节点")
            return nodes, routes, notes

        sales_id = "n_sales_confirm"
        sales_node = {
            "id": sales_id,
            "type": "approval",
            "name": "业务员确认",
            "approver_rule": {
                "type": "form_field_person",
                "value": ["yes_sales_person", "no_sales_person"],
            },
            "multi_mode": "or_sign",
            "empty_strategy": "auto_approve",
            "field_perms": [
                {"field": "confirm_agreement", "access": "required"},
            ],
        }
        end_idx = next((i for i, n in enumerate(nodes) if n.get("id") == "end"), len(nodes))
        nodes.insert(end_idx, sales_node)

        retargeted = False
        for r in routes:
            if (
                r.get("source") == "start"
                and r.get("target") == dept["id"]
                and not r.get("condition")
                and not r.get("always")
            ):
                r["target"] = sales_id
                retargeted = True
        if not retargeted:
            routes.append({"id": "r_start_sales", "source": "start", "target": sales_id})
        notes.append(
            "补齐「业务员确认」（JDY 画布 V43；审批人=（是）/（否）业务人员；"
            "其后按区域经理/组长是否为空分支）"
        )

    if apply_prod_card_sales_before_region(nodes, routes):
        notes.append(
            "校正：区域经理/组长挂在业务员确认之后（先确认再区域）"
        )
    return nodes, routes, notes


def main():
    fields_raw = json.loads((OUT / "_jdy_prod_card_fields.json").read_text(encoding="utf-8"))
    wf_raw = json.loads((OUT / "_jdy_prod_card_workflows_raw.json").read_text(encoding="utf-8"))
    linkage = load_linkage_pack()
    required_widgets, rule_widgets, _ = collect_linkage_sets(linkage)
    fields = build_fields(fields_raw, required_widgets, rule_widgets)
    rules = build_rule_definitions(linkage, fields)
    nodes, routes, notes = build_flow(wf_raw, fields, TITLE)
    nodes, routes, notes = patch_sales_confirm_node(nodes, routes, notes)
    from app.domains.lowcode.workflow_service import apply_prod_card_notify_production_cc
    if apply_prod_card_notify_production_cc(nodes):
        notes.append("通知生产启用抄送：吕英萍、雷贤、吴超（对齐简道云）")

    result = {
        KEY: {
            "name": TITLE,
            "field_definitions": fields,
            "rule_definitions": rules,
            "flow_nodes": nodes,
            "flow_routes": routes,
            "notes": notes,
        }
    }

    n_req = sum(1 for f in fields if f.get("required"))
    n_req_cols = sum(
        1 for f in fields for c in (f.get("detail_table_columns") or []) if c.get("required")
    )
    n_vis = sum(1 for r in rules if r.get("type") == "visibility")
    n_req_r = sum(1 for r in rules if r.get("type") == "required")

    md = [
        "# 生产卡/补充流程 — CRM 字段对照",
        "",
        "> 简道云 app=`56ca77ce1efc301d279b8a4d` entry=`5d11dcbf0c9b52255a2cb4be`",
        "> 必填/显隐：`_jdy_prod_card_edit_raw.json` → `_jdy_prod_card_linkages.json`",
        "",
        f"- **builtin key**: `{KEY}`",
        f"- **路由**: `/prod-card-supplements`",
        f"- **字段数（去噪后）**: {len(fields)}",
        f"- **必填字段**: {n_req}" + (f"（含子表列 {n_req_cols}）" if n_req_cols else ""),
        f"- **规则**: 显隐 {n_vis} / 条件必填 {n_req_r}",
        f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
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
    md += ["", "### 显隐 / 条件必填规则", ""]
    if not rules:
        md.append("- （无）")
    else:
        md.append("| id | type | target | condition |")
        md.append("|----|------|--------|-----------|")
        for r in rules:
            md.append(
                f"| `{r['id']}` | {r['type']} | `{r.get('target_field_id', '')}` | "
                f"{_cond_summary(r.get('condition') or {})} |"
            )
    md += ["", "### 流程降级备注", ""]
    for n in notes:
        md.append(f"- {n}")
    md.append("")

    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
        "\"\"\"Auto-generated from docs/product/_jdy_prod_card_* dumps. Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"PROD_CARD_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    (OUT / "_jdy_prod_card_forms.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        f"{KEY}: fields={len(fields)} required={n_req}+cols{n_req_cols} "
        f"rules={len(rules)}(vis={n_vis},req={n_req_r}) "
        f"nodes={len(nodes)} routes={len(routes)}"
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
