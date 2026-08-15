# -*- coding: utf-8 -*-
"""Generate CRM builtin 中央研究院协同卡 from JDY dumps.

Sources:
  docs/product/_jdy_research_coop_card_{fields,workflows_raw,edit_raw}.json
Output:
  backend/app/domains/lowcode/_research_coop_card_generated.py
  docs/product/_jdy_research_coop_card_linkages.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gen_drawing_jdy import (  # noqa: E402
    apply_pickable_scope,
    build_flow,
    build_rule_definitions,
    label_of,
    load_widget_limits_from_edit_raw,
    map_type,
    options_of,
)

OUT = Path(r"g:\ruolin-a\spt-crm\docs\product")
GEN = Path(r"g:\ruolin-a\spt-crm\backend\app\domains\lowcode\_research_coop_card_generated.py")
LINK_OUT = OUT / "_jdy_research_coop_card_linkages.json"

SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}
HARD_DROP = ("取消", "停用", "不用显示", "250423取消")

TITLE_SLUG = {
    "流水号": "serial_no",
    "协同卡类型": "coop_card_type",
    "流程名称": "process_name",
    "选择安装图设计通知数据": "link_install",
    "流水号-安装图设计通知": "install_serial_no",
    "订货人（文本）-安装图设计通知": "install_order_person",
    "申请人-安装图设计通知": "install_applicant",
    "新设计卡号-安装图设计通知": "install_design_card_no",
    "对应项目号-安装图设计通知": "install_project_no",
    "部门-安装图设计通知": "install_department",
    "合同图纸（资料）领用申请": "link_requisition",
    "流水号-合同图纸（资料）领用申请": "req_serial_no",
    "合同号-合同图纸（资料）领用申请": "req_contract_no",
    "申请人-合同图纸（资料）领用申请": "req_applicant",
    "订货人（文本）-合同图纸（资料）领用申请": "req_order_person",
    "部门-合同图纸（资料）领用申请": "req_department",
    "客服领图": "link_cs_drawing",
    "流水号-客服领图": "cs_serial_no",
    "部门-客服领图": "cs_department",
    "申请人-客服领图": "cs_applicant",
    "合同号-客服领图": "cs_contract_no",
    "订货人*-客服领图": "cs_order_person",
    "生产卡/补充流程": "link_prod_card",
    "1.2.8生产卡/补充流程编号": "prod_card_no",
    "图纸编号（筛选用）（公式的）-生产卡/补充流程": "prod_drawing_no",
    "申请人-生产卡/补充流程": "prod_applicant",
    "所在部门-生产卡/补充流程": "prod_department",
    "流水号（合并）": "merged_serial_no",
    "对应项目号": "project_no",
    "对应设计卡号（合并）": "design_card_no",
    "合同号（合并）": "contract_no",
    "订货人（合并）": "order_person_merged",
    "申请人（合并）": "applicant_merged",
    "业务部门（合并）": "business_dept_merged",
    "合同信息*": "link_contract",
    "订货部门*": "order_dept",
    "订货人*": "order_person",
    "图纸编号*": "drawing_no",
    "下卡日期": "card_date",
    "图纸编号-通用": "drawing_no_generic",
    "订货部门": "order_dept_generic",
    "订货人": "order_person_generic",
    "申请人": "applicant",
    "所属科室": "office",
    "设备名称": "equipment_name",
    "规格型号（内部型号）": "spec_model",
    "设备数量": "equipment_qty",
    "是否需要对照技术协议": "need_tech_agreement",
    "协同图纸要求完成时间": "coop_draw_due",
    "全套图纸下图时间": "full_draw_date",
    "电气1": "elec_motors",
    "激振器电机": "vibrator_motor",
    "功率（KW)": "power_kw",
    "数量": "qty",
    "其他电机": "other_motor",
    "工艺要求1": "process_req",
    "外设仪表1": "external_meters",
    "激振器2": "vibrator_params",
    "项目": "item_name",
    "预设值": "preset_value",
    "确认值": "confirm_value",
    "行号": "row_no",
    "激振器类型-预设值": "vibrator_type_preset",
    "激振器类型-确认值": "vibrator_type_confirm",
    "是否带加热-预设值": "has_heat_preset",
    "是否带加热-确认值": "has_heat_confirm",
    "筛板3": "screen_deck",
    "物料名称": "material_name",
    "物料堆比重": "bulk_density",
    "入料粒度": "feed_size",
    "物料含水量": "moisture",
    "物料温度": "material_temp",
    "分级粒度": "grade_size",
    "筛板类型3": "screen_type",
    "要求完成时间4": "std_due_date",
    "标准化内容简述4": "std_summary",
    "详细要求4": "std_detail",
    "主设提醒": "chief_design_note",
    "协同项目名称": "coop_project_name",
    "交图时间": "delivery_draw_date",
    "是否含技术协议": "has_tech_agreement",
    "协同内容及主设设计思路": "coop_content",
    "附件名称": "attachment_names",
    "附件": "attachments",
    "图片": "images",
    "设计单分派": "design_dispatch",
    "转新乡、工艺包装": "transfer_packaging_users",
    "设计指派": "design_assignees",
    "科室": "offices",
    "下单时间": "order_datetime",
}

FORM = {
    "key": "research_coop_card",
    "title": "中央研究院协同卡",
    "entry": "63acddd2129b90000a2933f1",
    "fields_file": "_jdy_research_coop_card_fields.json",
    "wf_file": "_jdy_research_coop_card_workflows_raw.json",
    "edit_file": "_jdy_research_coop_card_edit_raw.json",
}

# 流程名称显隐兜底（edit_raw 规则为主，本组补关联块）
VIS_PROCESS = {
    "安装图设计通知": [
        "link_install", "install_serial_no", "install_order_person",
        "install_applicant", "install_design_card_no", "install_project_no",
        "install_department",
    ],
    "合同图纸（资料）领用申请": [
        "link_requisition", "req_serial_no", "req_contract_no",
        "req_applicant", "req_order_person", "req_department",
    ],
    "客服领图": [
        "link_cs_drawing", "cs_serial_no", "cs_department",
        "cs_applicant", "cs_contract_no", "cs_order_person",
    ],
    "生产卡/补充流程": [
        "link_prod_card", "prod_card_no", "prod_drawing_no",
        "prod_applicant", "prod_department",
    ],
}


def should_keep(label: str, name: str, typ0: str) -> bool:
    if name in SYS_IDS:
        return False
    if typ0 in SKIP_TYPES:
        return False
    lab = label or ""
    if not lab or lab.startswith("_"):
        return False
    if any(k in lab for k in HARD_DROP):
        return False
    return True


def _slug_for(label: str, typ0: str, used: set[str]) -> str:
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
        typ0 = (c.get("type") or "").lower()
        if not should_keep(lab, name, typ0):
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        if typ == "detail_table":
            continue
        opts = options_of(c)
        if typ == "select" and not opts:
            typ = "text"
        fd = {"id": _slug_for(lab, typ0, used), "type": typ, "label": lab.rstrip("*")}
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def build_fields(raw: dict, widget_limits: dict | None = None) -> list[dict]:
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out: list[dict] = []
    limits = widget_limits or {}
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f) or ""
        name = f.get("name") or ""
        if typ0 == "sn":
            fd = {
                "id": "serial_no",
                "type": "auto_number",
                "label": "流水号",
                "props": {
                    "serial_rules": [
                        {"type": "text", "value": "6.19.1-"},
                        {"type": "date", "format": "yyyyMMdd"},
                        {
                            "type": "counter",
                            "digits": 2,
                            "fixed": True,
                            "reset_period": "daily",
                            "initial_value": 1,
                        },
                    ],
                },
                "available_on_create": True,
                "fill_stage": "initiator",
                "form_editable": False,
            }
            used.add("serial_no")
            if name:
                fd["jdy_widget"] = name
            out.append(fd)
            continue
        if not should_keep(lab, name, typ0):
            continue
        slug = _slug_for(lab, typ0, used)
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        if typ0 in ("image", "upload"):
            typ = "file"
        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"
        fd: dict = {"id": slug, "type": typ, "label": lab.rstrip("*")}
        if f.get("required") or lab.endswith("*"):
            fd["required"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used)
            if not cols:
                continue
            fd["detail_table_columns"] = cols
        if name:
            fd["jdy_widget"] = name
        if typ in ("person", "person_multi"):
            apply_pickable_scope(fd, limit=limits.get(name), jdy_field=f)
        if typ == "date" or typ0 == "datetime":
            # 下卡日期等业务上按日
            if slug in ("card_date", "coop_draw_due", "full_draw_date", "std_due_date", "delivery_draw_date"):
                fd["type"] = "date"
                fd["props"] = {"show_time": False, "date_only": True}
        fd.setdefault("available_on_create", True)
        fd.setdefault("fill_stage", "initiator")
        out.append(fd)
    return out


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def normalize_show_rules(content: dict) -> list[dict]:
    """JDY 新版 fieldShowRules: {filter:{cond,rel}, fields:[widgetIds]} → 旧格式。"""
    out = []
    for rule in content.get("fieldShowRules") or []:
        if not isinstance(rule, dict):
            continue
        if rule.get("show_fields") or rule.get("conditions"):
            out.append(rule)
            continue
        filt = rule.get("filter") or {}
        conds = filt.get("cond") or []
        fields = rule.get("fields") or []
        mapped_conds = []
        for c in conds:
            if not isinstance(c, dict):
                continue
            mapped_conds.append({
                "field": c.get("field"),
                "method": c.get("method") or "eq",
                "value": c.get("value"),
            })
        out.append({
            "rel": filt.get("rel") or "and",
            "conditions": mapped_conds,
            "show_fields": [{"widget": w} for w in fields if w],
        })
    return out


def extract_linkages(edit_raw: dict) -> dict:
    content = edit_raw.get("content") or {}
    if isinstance(content, str):
        content = json.loads(content)
    show = normalize_show_rules(content if isinstance(content, dict) else {})
    return {
        "fieldShowRules": show,
        "subformFieldShowRules": (content or {}).get("subformFieldShowRules") or [],
        "show_rule_count": len(show),
    }


def build_process_vis_rules(fields: list[dict]) -> list[dict]:
    ids = {f["id"] for f in fields}
    rules = []
    for process_val, targets in VIS_PROCESS.items():
        present = [t for t in targets if t in ids]
        if not present:
            continue
        rules.append({
            "id": f"vis_process_{abs(hash(process_val)) % 10_000_000}",
            "type": "visibility",
            "target_field_ids": present,
            "condition": {"field": "process_name", "operator": "eq", "value": process_val},
            "action": {"visible": True},
        })
    return rules


def gen_one() -> dict:
    fields_raw = json.loads((OUT / FORM["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / FORM["wf_file"]).read_text(encoding="utf-8")))
    edit_raw = json.loads((OUT / FORM["edit_file"]).read_text(encoding="utf-8"))
    widget_limits = load_widget_limits_from_edit_raw(OUT / FORM["edit_file"])
    fields = build_fields(fields_raw, widget_limits)

    for fd in fields:
        if fd["id"] in ("coop_card_type", "process_name", "applicant"):
            fd["required"] = True

    linkages = extract_linkages(edit_raw)
    LINK_OUT.write_text(json.dumps(linkages, ensure_ascii=False, indent=2), encoding="utf-8")

    rules = build_rule_definitions(linkages, fields)
    # 补流程名称关联块（与 JDY showRules 并存，不覆盖）
    existing_targets = set()
    for r in rules:
        if r.get("target_field_id"):
            existing_targets.add(r["target_field_id"])
        for t in r.get("target_field_ids") or []:
            existing_targets.add(t)
    for r in build_process_vis_rules(fields):
        # 仅补尚未被 showRules 覆盖的关联字段组
        missing = [t for t in (r.get("target_field_ids") or []) if t not in existing_targets]
        if missing:
            rr = dict(r)
            rr["target_field_ids"] = missing
            rules.append(rr)

    nodes, routes, notes = build_flow(wf_raw, fields, FORM["title"])

    pack = {
        FORM["key"]: {
            "name": FORM["title"],
            "field_definitions": fields,
            "rule_definitions": rules,
            "flow_nodes": nodes,
            "flow_routes": routes,
            "notes": notes,
            "jdy": {
                "app": "584658417562f37a227fa805",
                "entry": FORM["entry"],
                "menu": "中央研究院 / 中央研究院协同卡",
            },
        }
    }
    return pack


def main() -> None:
    pack = gen_one()
    one = pack[FORM["key"]]
    GEN.write_text(
        "# -*- coding: utf-8 -*-\n"
        '"""Auto-generated from docs/product/_jdy_research_coop_card_* dumps. Do not edit by hand."""\n'
        "from __future__ import annotations\n"
        "import json\n\n"
        f"RESEARCH_COOP_CARD_JDY = json.loads(r'''{json.dumps(pack, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print(
        f"wrote {GEN.name} fields={len(one['field_definitions'])} "
        f"rules={len(one['rule_definitions'])} "
        f"nodes={len(one['flow_nodes'])} routes={len(one['flow_routes'])}"
    )
    for n in one["notes"][:15]:
        print(" note:", n)


if __name__ == "__main__":
    main()
