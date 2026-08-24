# -*- coding: utf-8 -*-
"""Generate CRM builtins from JDY 技术协议反馈单 + 合同外购件提前安排流程 dumps.

Sources:
  docs/product/_jdy_tech_agreement_feedback_{fields,workflows_raw,edit_raw}.json
  docs/product/_jdy_contract_outsource_early_{fields,workflows_raw,edit_raw}.json
Output:
  backend/app/domains/lowcode/_tech_feedback_outsource_generated.py
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
    label_of,
    load_widget_limits_from_edit_raw,
    map_condition,
    map_type,
    options_of,
    or_merge,
    widget_slug_map,
)

OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
GEN = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "domains"
    / "lowcode"
    / "_tech_feedback_outsource_generated.py"
)

SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id", "flowState"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}
HARD_DROP_KEYS = ("取消", "停用", "不用显示")
HARD_DROP_LABELS = frozenset({"占位置不再经总经理260709"})

FORMS = [
    {
        "key": "tech_agreement_feedback",
        "title": "技术协议反馈单",
        "entry": "5e707cbf45da660006ec37c7",
        "app": "584658417562f37a227fa805",
        "menu": "中央研究院 / 技术协议反馈单",
        "route": "/tech-agreement-feedbacks",
        "fields_file": "_jdy_tech_agreement_feedback_fields.json",
        "wf_file": "_jdy_tech_agreement_feedback_workflows_raw.json",
        "edit_file": "_jdy_tech_agreement_feedback_edit_raw.json",
        "md_file": "_jdy_tech_agreement_feedback_forms.md",
    },
    {
        "key": "contract_outsource_early",
        "title": "合同外购件提前安排流程",
        "entry": "638ab9b444b934000aba26ce",
        "app": "56ca77ce1efc301d279b8a4d",
        "menu": "数据中心 / 合同管理 / 合同外购件提前安排流程",
        "route": "/contract-outsource-early",
        "fields_file": "_jdy_contract_outsource_early_fields.json",
        "wf_file": "_jdy_contract_outsource_early_workflows_raw.json",
        "edit_file": "_jdy_contract_outsource_early_edit_raw.json",
        "md_file": "_jdy_contract_outsource_early_forms.md",
    },
]

TECH_TITLE_SLUG = {
    "流水号": "serial_no",
    "日期时间": "apply_datetime",
    "申请人": "applicant",
    "科室": "office",
    "合同号": "contract_no",
    "订货人": "order_person",
    "所属部门": "department",
    "设计审核人": "design_reviewer",
    "是否通知采购": "notify_purchase",
    "设计单分派": "design_dispatch",
    "转新乡、郑州研发中心": "transfer_rd_centers",
    "部门内勤": "dept_clerk",
    "业务员": "salesperson",
    "协议内容": "agreement_content",
    "业务反馈": "business_feedback",
    "反馈建议": "feedback_suggestion",
    "附件": "attachments",
    "图片": "images",
}

OUTSOURCE_TITLE_SLUG = {
    "流水号": "serial_no",
    "日期时间": "apply_datetime",
    "选择生产卡/补充数据": "link_prod_card",
    "1.2.8生产卡/补充流程编号": "prod_card_serial",
    "业务员": "salesperson",
    "部门": "department",
    "合同号": "contract_no",
    "设计指派": "design_assign",
    "科室": "office",
    "业务描述": "business_desc",
    "备注": "remark",
    "附件": "attachments",
    "转交科室主任（多人）": "transfer_dept_heads",
    "转交科室主任（单人）": "transfer_dept_head",
    "设计员（单选）": "designer_single",
    "设计员（多选）": "designer_multi",
    "采购员多选": "purchaser_multi",
    "设备明细": "equipment_details",
    "设计员": "designer",
    "产品名称": "product_name",
    "规格型号": "spec_model",
    "材质": "material",
    "数量": "qty",
    "品牌": "brand",
    "颜色": "color",
    "电机接线盒方向": "motor_junction_dir",
    "铭牌要求": "nameplate_req",
    "随机资料要求": "random_docs_req",
}

TECH_APPROVER_FILL = frozenset({"business_feedback", "feedback_suggestion"})
OUTSOURCE_APPROVER_FILL = frozenset({
    "design_assign", "transfer_dept_heads", "transfer_dept_head",
    "designer_single", "designer_multi", "purchaser_multi",
})

_RESET_MAP = {
    "none": "none",
    "day": "daily",
    "month": "monthly",
    "year": "yearly",
}


def is_hard_drop(label: str, name: str) -> bool:
    if name in SYS_IDS:
        return True
    lab = (label or "").strip()
    if not lab or lab.startswith("_"):
        return True
    if lab in HARD_DROP_LABELS:
        return True
    return any(k in lab for k in HARD_DROP_KEYS)


def should_keep_field(label: str, name: str, typ0: str, *, key: str) -> bool:
    if is_hard_drop(label, name):
        return False
    if typ0 in SKIP_TYPES:
        return False
    if key == "tech_agreement_feedback" and label == "表单名称":
        return False
    return True


def _slug_for(label: str, typ0: str, used: set[str], slug_map: dict[str, str]) -> str:
    base = slug_map.get(label)
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


def _reset_period(jdy_reset: str | None) -> str:
    return _RESET_MAP.get(str(jdy_reset or "none").lower(), "none")


def _parse_sn_rules(rules: list) -> list[dict]:
    out: list[dict] = []
    for r in rules or []:
        if not isinstance(r, dict):
            continue
        typ = r.get("type")
        if typ == "fixedChars" and r.get("chars"):
            out.append({"type": "text", "value": str(r["chars"])})
        elif typ == "createTime":
            out.append({"type": "date", "format": str(r.get("format") or "yyyyMMdd")})
        elif typ == "incNumber":
            out.append({
                "type": "counter",
                "digits": int(r.get("digitsNum") or 3),
                "fixed": bool(r.get("fixedLength", True)),
                "reset_period": _reset_period(r.get("resetDuration")),
                "initial_value": int(r.get("startValue") or 1),
            })
    return out


def load_edit_raw_widgets(path: Path) -> tuple[dict[str, bool], dict[str, list], dict[str, list]]:
    """widgetName -> allowBlank(required=False), sn rules, fieldShowRules list on content."""
    if not path.exists():
        return {}, {}, {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    content = raw.get("content") or raw.get("data") or raw
    required: dict[str, bool] = {}
    sn_rules: dict[str, list] = {}

    def walk(node):
        if isinstance(node, dict):
            w = node.get("widget") if isinstance(node.get("widget"), dict) else node
            name = w.get("widgetName") or w.get("name") or node.get("name")
            if name:
                if "allowBlank" in w:
                    required[str(name)] = not bool(w.get("allowBlank"))
                if (w.get("type") or "").lower() == "sn":
                    sn_rules[str(name)] = _parse_sn_rules(w.get("rules") or [])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)

    walk(content.get("items") or [])
    fsr = content.get("fieldShowRules") or []
    if isinstance(content.get("attr"), dict):
        link = content["attr"].get("linkage") or {}
        if link.get("fieldShowRules"):
            fsr = link["fieldShowRules"]
    return required, sn_rules, fsr if isinstance(fsr, list) else []


def sub_columns(
    f: dict, used: set[str], slug_map: dict[str, str], key: str,
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
        typ0 = (c.get("type") or "").lower()
        if not should_keep_field(lab, name, typ0, key=key):
            continue
        if typ0 in SKIP_TYPES:
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        if typ == "detail_table":
            continue
        opts = options_of(c)
        if typ == "select" and not opts:
            typ = "text"
        fd = {"id": _slug_for(lab, typ0, used, slug_map), "type": typ, "label": lab}
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        out.append(fd)
    return out


def build_fields(
    raw: dict,
    meta: dict,
    widget_limits: dict[str, dict] | None = None,
    required_widgets: dict[str, bool] | None = None,
    sn_by_widget: dict[str, list] | None = None,
) -> list[dict]:
    key = meta["key"]
    slug_map = TECH_TITLE_SLUG if key == "tech_agreement_feedback" else OUTSOURCE_TITLE_SLUG
    approver_fill = TECH_APPROVER_FILL if key == "tech_agreement_feedback" else OUTSOURCE_APPROVER_FILL
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out: list[dict] = []
    limits = widget_limits or {}
    req = required_widgets or {}
    sn_map = sn_by_widget or {}

    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f)
        name = f.get("name") or ""
        if typ0 in SKIP_TYPES:
            continue
        if not lab or not should_keep_field(lab, name, typ0, key=key):
            continue

        if typ0 == "sn":
            rules = sn_map.get(name) or []
            fd = {
                "id": "serial_no",
                "type": "auto_number",
                "label": "流水号",
                "props": {"serial_rules": rules or [{"type": "date", "format": "yyyyMMdd"}]},
                "available_on_create": True,
                "fill_stage": "initiator",
                "form_editable": False,
            }
            used.add("serial_no")
            if name:
                fd["jdy_widget"] = name
            if req.get(name):
                pass  # serial auto
            out.append(fd)
            continue

        slug = _slug_for(lab, typ0, used, slug_map)
        typ = map_type(typ0)

        if typ0 == "combo" and lab == "合同号":
            typ = "contract"
        elif typ0 == "linkfield" and slug == "link_prod_card":
            typ = "select_data"
        elif typ0 == "linkfield":
            typ = "text"
        if typ0 == "image":
            typ = "file"

        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"

        fd: dict = {"id": slug, "type": typ, "label": lab}
        if typ == "contract":
            fd["description"] = "从合同管理中选择。"
        if typ == "select_data" and slug == "link_prod_card":
            fd["label"] = "选择生产卡/补充数据"
            fd["description"] = "从生产卡/补充流程中选择；选中后自动带出流程编号。"
            fd["required"] = True
            props = dict(fd.get("props") or {})
            props["source_form_code"] = "prod_card_supplement"
            props["link_fill"] = "contract_outsource_prod_card"
            fd["props"] = props
        if slug == "prod_card_serial":
            fd["form_editable"] = False
            fd["description"] = "由所选生产卡/补充流程自动带出，不可手改。"
        if req.get(name) or f.get("required"):
            fd["required"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used, slug_map, key)
            if cols:
                fd["detail_table_columns"] = cols
            else:
                continue
        if name:
            fd["jdy_widget"] = name
        if typ in ("person", "person_multi"):
            apply_pickable_scope(fd, limit=limits.get(name), jdy_field=f)
        if slug in approver_fill:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
        else:
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")
        if slug == "applicant":
            props = dict(fd.get("props") or {})
            props["default_current_user"] = True
            fd["props"] = props
        if slug == "apply_datetime":
            props = dict(fd.get("props") or {})
            props["default_today"] = True
            props.setdefault("date_only", True)
            props.setdefault("show_time", False)
            fd["props"] = props
        out.append(fd)
    return out


def build_rules_from_linkage(fields: list[dict], field_show_rules: list) -> list[dict]:
    widget_slug = widget_slug_map(fields)
    by_target: dict[str, list[dict]] = {}
    for rule in field_show_rules or []:
        filt = rule.get("filter") or {}
        cond = map_condition(filt, widget_slug)
        if not cond:
            continue
        for wid in rule.get("fields") or rule.get("show_fields") or []:
            if isinstance(wid, dict):
                wid = wid.get("widget") or wid.get("name")
            slug = widget_slug.get(wid) if wid else None
            if not slug:
                continue
            by_target.setdefault(slug, []).append(cond)

    rules: list[dict] = []
    for slug, conds in by_target.items():
        uniq: list[dict] = []
        seen: set[str] = set()
        for c in conds:
            key = json.dumps(c, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(c)
        merged = or_merge(uniq)
        rules.append({
            "id": f"vis_{slug}",
            "type": "visibility",
            "target_field_id": slug,
            "condition": merged,
            "action": {"visible": True},
        })
        if slug in ("transfer_rd_centers", "business_feedback"):
            rules.append({
                "id": f"req_{slug}",
                "type": "required",
                "target_field_id": slug,
                "condition": merged,
                "action": {"required": True},
            })
    return rules


def _approval_node(nid: str, name: str, rule: dict, *, field_ids: list[str] | None = None) -> dict:
    node: dict = {
        "id": nid,
        "type": "approval",
        "name": name,
        "approver_rule": rule,
        "multi_mode": "or_sign",
        "empty_strategy": "auto_approve",
    }
    if field_ids:
        node["field_perms"] = [{"field": fid, "access": "editable"} for fid in field_ids]
    return node


def _cc_node(nid: str, name: str, rule: dict) -> dict:
    return {"id": nid, "type": "cc", "name": name, "approver_rule": rule}


def _restore_initiator_field_flags(
    fields: list[dict],
    required_widgets: dict[str, bool],
    key: str,
) -> None:
    """build_flow/optAuth 未取到时，恢复发起阶段可填与 allowBlank。"""
    approver_fill = TECH_APPROVER_FILL if key == "tech_agreement_feedback" else OUTSOURCE_APPROVER_FILL
    for fd in fields:
        fid = fd.get("id")
        if fid in approver_fill:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            continue
        if fid == "serial_no":
            fd["available_on_create"] = True
            fd["fill_stage"] = "initiator"
            continue
        if fid == "prod_card_serial":
            fd["form_editable"] = False
        wname = fd.get("jdy_widget")
        if wname and required_widgets.get(str(wname)):
            fd["required"] = True
        fd.setdefault("available_on_create", True)
        fd.setdefault("fill_stage", "initiator")
    if key == "tech_agreement_feedback":
        for fd in fields:
            if fd.get("id") in ("transfer_rd_centers", "business_feedback"):
                fd["required"] = False


def fallback_flow(key: str, fields: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """JDY workflow_config 未取到时，按字段名推断多节点审批流。"""
    ids = {f["id"] for f in fields}
    notes = [
        "简道云 workflow_config 未取到（configs API 返回空/HTML）；"
        "以下为按表单人员字段推断的 CRM 兜底审批拓扑，上线后宜对照实单校正。",
    ]
    nodes: list[dict] = [{"id": "start", "type": "start", "name": "发起"}]
    routes: list[dict] = []
    prev = "start"
    ri = 0

    def link(src: str, tgt: str) -> None:
        nonlocal ri
        ri += 1
        routes.append({"id": f"r_{ri}", "source": src, "target": tgt})

    if key == "tech_agreement_feedback":
        from app.domains.lowcode.workflow_service import build_tech_agreement_feedback_flow
        nodes, routes = build_tech_agreement_feedback_flow()
        notes = [
            "简道云 workflow_config 未取到（中央研究院 app 未接入 data-hub）；"
            "按流程设计实单重建 CRM 拓扑。",
            "发起抄业务员 → 设计审核 → 总工意见 ∥ 内勤安排 → 内勤核查 → "
            "（业务员空/非空）→ 财务核算 → 部门意见 → 总经理审批 → 通知抄送。",
        ]
        return nodes, routes, notes
    else:
        steps = []
        if "design_assign" in ids:
            steps.append(_approval_node(
                "n_design_assign", "设计指派",
                {"type": "form_field_person_multi", "value": "design_assign"},
                field_ids=["design_assign"] if "design_assign" in ids else None,
            ))
        if "transfer_dept_head" in ids:
            steps.append(_approval_node(
                "n_dept_head", "科室主任",
                {"type": "form_field_person", "value": "transfer_dept_head"},
                field_ids=["transfer_dept_head"] if "transfer_dept_head" in ids else None,
            ))
        if "designer_single" in ids:
            steps.append(_approval_node(
                "n_designer", "设计员",
                {"type": "form_field_person", "value": "designer_single"},
                field_ids=["designer_single"] if "designer_single" in ids else None,
            ))
        if "purchaser_multi" in ids:
            steps.append(_approval_node(
                "n_purchaser", "采购安排",
                {"type": "form_field_person_multi", "value": "purchaser_multi"},
                field_ids=["purchaser_multi"] if "purchaser_multi" in ids else None,
            ))
        for step in steps:
            nodes.append(step)
            link(prev, step["id"])
            prev = step["id"]
        if "salesperson" in ids:
            cc = _cc_node("cc_sales", "抄送业务员", {
                "type": "form_field_person", "value": "salesperson",
            })
            nodes.append(cc)
            link(prev, cc["id"])
            prev = cc["id"]
            routes.append({"id": f"r_{ri + 1}", "source": cc["id"], "target": "end", "always": True})
        notes.append("兜底：设计指派→科室主任→设计员→采购安排→抄送业务员。")

    nodes.append({"id": "end", "type": "end", "name": "结束"})
    if prev != "end" and not any(r.get("source") == prev and r.get("target") == "end" for r in routes):
        ri += 1
        routes.append({"id": f"r_{ri}", "source": prev, "target": "end"})
    return nodes, routes, notes


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def gen_one(meta: dict) -> dict:
    key = meta["key"]
    fields_raw = json.loads((OUT / meta["fields_file"]).read_text(encoding="utf-8"))
    wf_raw = unwrap_wf(json.loads((OUT / meta["wf_file"]).read_text(encoding="utf-8")))
    edit_path = OUT / meta["edit_file"]
    widget_limits = load_widget_limits_from_edit_raw(edit_path)
    required_widgets, sn_by_widget, fsr = load_edit_raw_widgets(edit_path)
    fields = build_fields(
        fields_raw, meta, widget_limits, required_widgets, sn_by_widget,
    )

    # 条件必填：设计单分派联动字段在创建阶段先放宽
    if key == "tech_agreement_feedback":
        for fd in fields:
            if fd["id"] in ("transfer_rd_centers", "business_feedback"):
                fd["required"] = False

    rules = build_rules_from_linkage(fields, fsr)
    wf_inner = (wf_raw.get("workflow_config") or {}) if isinstance(wf_raw, dict) else {}
    flows = wf_inner.get("flows") or []
    if flows:
        nodes, routes, notes = build_flow(wf_raw, fields, meta["title"])
        if len([n for n in nodes if n.get("type") == "approval"]) < 1:
            nodes, routes, notes = fallback_flow(key, fields)
    else:
        nodes, routes, notes = fallback_flow(key, fields)
    _restore_initiator_field_flags(fields, required_widgets, key)

    pack = {
        "name": meta["title"],
        "field_definitions": fields,
        "rule_definitions": rules,
        "flow_nodes": nodes,
        "flow_routes": routes,
        "notes": notes,
        "jdy": {"app": meta["app"], "entry": meta["entry"], "menu": meta["menu"]},
    }

    n_req = sum(1 for f in fields if f.get("required"))
    md = [
        f"# {meta['title']} — CRM 字段对照",
        "",
        f"> 简道云 app=`{meta['app']}` entry=`{meta['entry']}`",
        "",
        f"- **builtin key**: `{key}`",
        f"- **路由**: `{meta['route']}`",
        f"- **字段数（去噪后）**: {len(fields)}",
        f"- **静态必填**: {n_req}",
        f"- **流程节点数（CRM）**: {len(nodes)} / 连线 {len(routes)}",
        f"- **联动规则**: {len(rules)}",
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
    md += ["", "### 流程备注", ""]
    for n in notes:
        md.append(f"- {n}")
    md.append("")
    (OUT / meta["md_file"]).write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        f"{key}: fields={len(fields)} required={n_req} "
        f"nodes={len(nodes)} routes={len(routes)} rules={len(rules)}"
    )
    return {key: pack}


def main() -> None:
    result: dict = {}
    for meta in FORMS:
        result.update(gen_one(meta))
    GEN.write_text(
        "# -*- coding: utf-8 -*-\n"
        '"""Auto-generated from docs/product/_jdy_tech_agreement_feedback_* '
        'and _jdy_contract_outsource_early_* dumps. Do not edit by hand."""\n'
        "from __future__ import annotations\n"
        "import json\n\n"
        f"TECH_FEEDBACK_OUTSOURCE_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
