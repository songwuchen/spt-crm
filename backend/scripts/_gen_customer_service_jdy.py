# -*- coding: utf-8 -*-
"""Generate CRM customer-service builtins from JDY dumps.

Sources: docs/product/_jdy_cs_*_{fields,workflows_raw}.json
Output: backend/app/domains/lowcode/_customer_service_jdy_generated.py
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
    map_type,
    options_of,
)

OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
GEN = Path(__file__).resolve().parents[1] / "app" / "domains" / "lowcode" / "_customer_service_jdy_generated.py"
MATCHED = OUT / "_jdy_customer_service_matched.json"
LINKAGES = OUT / "_jdy_customer_service_linkages.json"

SOFT_NOISE_KEYS = (
    "辅助", "已取消", "打印模板", "筛选用", "公式的", "主键", "离职",
    "按日统计", "周几", "当日回款", "目标数",
)
HARD_DROP_KEYS = ("取消", "停用", "不用显示", "22/11/28", "230320", "221209", "240311", "删关")
# 简道云「订货人*/设计人*」为人员旁文本镜像，CRM 只保留人员选择器
STAR_TEXT_DROP = frozenset({"订货人*", "设计人*"})
SYS_IDS = {"creator", "createTime", "updateTime", "appId", "entryId", "_id"}
SKIP_TYPES = {
    "separator", "button", "pagebreak", "hint", "flowstate",
    "aggregation", "linkquery", "formula",
}

# shared title → slug
TITLE_SLUG = {
    "流程编号": "serial_no",
    "流水号": "serial_no",
    "部门": "department",
    "申请人": "applicant",
    "业务员": "sales_person",
    "客户名称": "customer_name",
    "公司名称": "customer_name",
    "单位名称": "customer_name",
    "合同号": "contract_no",
    "合同编号": "contract_no",
    "图纸编号": "drawing_no",
    "备注": "remark",
    "申请事由": "apply_reason",
    "申请事由*": "apply_reason",
    "事由": "apply_reason",
    "日期时间": "apply_datetime",
    "订货人": "order_person",
    "订货人*": "order_person_text",
    "订货人（文本）": "order_person_text",
    "设计人": "designer",
    "设计人(文本)": "designer_text",
    "设计人*": "designer_text",
    "产品型号": "product_model",
    "图纸传递途径": "transfer_channel",
    "附件": "attachments",
    "附件名称": "attachment_name",
    "图片": "images",
    "附件0418": "f_0418",
    "客服附件0418": "f_0418_2",
    "客服补登附件0418": "f_0418_3",
    "会签附件0418": "f_0418_4",
    "图片0418": "f_0418_5",
    "设计单分派": "design_dispatch",
    "设计指派": "design_assignees",
    "转新乡、工艺包装": "transfer_packaging_users",
    "科室": "offices",
    "下单日期": "order_date",
    "下单时间": "order_date",
    "部门指派": "dept_dispatch",
    "图号231021": "drawing_no_note",
}

FORMS_META = {
    "cs_service_request": {
        "title": "客户服务申请及反馈",
        "route": "/cs-service-requests",
        "serial_prefix": "KF",
    },
    "cs_product_replace": {
        "title": "售出产品更换（补发）",
        "route": "/cs-product-replaces",
        "serial_prefix": "GH",
        "serial_label": "流水号",
    },
    "cs_product_return": {
        "title": "售出产品/工具退回",
        "route": "/cs-product-returns",
        "serial_prefix": "TH",
    },
    "cs_loan_slip": {
        "title": "客服借据",
        "route": "/cs-loan-slips",
        "serial_prefix": "JJ",
    },
    "cs_service_delay": {
        "title": "客户服务延期申请",
        "route": "/cs-service-delays",
        "serial_prefix": "YQ",
    },
    "cs_correspondence": {
        "title": "客服往来函件",
        "route": "/cs-correspondences",
        "serial_prefix": "WH",
    },
    "cs_drawing_request": {
        "title": "客服领图",
        "route": "/cs-drawing-requests",
        # 简道云流水号：yyyyMMdd + 2位日序（无字母前缀）
        "serial_prefix": "",
        "serial_digits": 2,
    },
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


def should_keep_field(label: str, name: str) -> bool:
    if is_hard_drop(label, name):
        return False
    if is_soft_noise(label):
        return False
    if (label or "").strip() in STAR_TEXT_DROP:
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


def load_linkage_pack(form_key: str) -> dict:
    if not LINKAGES.exists():
        return {}
    data = json.loads(LINKAGES.read_text(encoding="utf-8"))
    return (data.get("forms") or {}).get(form_key) or {}


def load_required_widgets(form_key: str) -> set[str]:
    """从 edit_raw 抽出的 linkages：allowBlank===false → 必填 widget。"""
    pack = load_linkage_pack(form_key)
    out: set[str] = set()
    for r in pack.get("required_fields") or []:
        if isinstance(r, dict) and r.get("widget"):
            out.add(str(r["widget"]))
    return out


def _jdy_datetime_is_date_only(raw: dict) -> bool:
    """简道云 datetime 的 format 无时分 → CRM 仅选日期。"""
    fmt = str(raw.get("format") or "").strip().lower()
    if not fmt:
        return False
    return "h" not in fmt


def _apply_datetime_date_only_props(fd: dict, raw: dict) -> None:
    if fd.get("type") != "datetime":
        return
    if _jdy_datetime_is_date_only(raw):
        fd["props"] = {**(fd.get("props") or {}), "date_only": True, "show_time": False}


def sub_columns(f: dict, used: set[str], required_widgets: set[str] | None = None) -> list[dict]:
    req = required_widgets or set()
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
        if typ0 == "image":
            typ = "image"
        if typ == "detail_table":
            continue
        opts = options_of(c)
        if typ == "select" and not opts:
            typ = "text"
        slug = _slug_for(lab, used)
        if slug in ("contract_no", "drawing_no") or lab in ("合同号", "合同编号", "图纸编号"):
            typ = "contract"
            opts = []
            slug = "contract_no"
        fd = {"id": slug, "type": typ, "label": lab}
        if typ == "contract":
            fd["description"] = "从合同管理中选择；按图纸编号搜索，选项以图纸编号显示。"
        if name in req or c.get("required"):
            fd["required"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if name:
            fd["jdy_widget"] = name
        _apply_datetime_date_only_props(fd, c)
        out.append(fd)
    return out


def _serial_field(
    prefix: str,
    name: str = "",
    *,
    digits: int = 3,
    label: str | None = None,
) -> dict:
    rules: list[dict] = []
    if prefix:
        rules.append({"type": "text", "value": prefix})
    rules.append({"type": "date", "format": "yyyyMMdd"})
    rules.append({
        "type": "counter",
        "digits": max(1, int(digits or 3)),
        "fixed": True,
        "reset_period": "daily",
        "initial_value": 1,
    })
    fd = {
        "id": "serial_no",
        "type": "auto_number",
        "label": label or ("流水号" if not prefix else "流程编号"),
        "props": {"serial_rules": rules},
        "available_on_create": True,
        "fill_stage": "initiator",
        "form_editable": False,
    }
    if name:
        fd["jdy_widget"] = name
    return fd


def build_fields(
    raw: dict,
    serial_prefix: str,
    required_widgets: set[str] | None = None,
    *,
    serial_digits: int = 3,
    serial_label: str | None = None,
) -> list[dict]:
    req = required_widgets or set()
    data = raw.get("data", raw)
    fields = data.get("fields") if isinstance(data, dict) else data
    used: set[str] = set()
    out: list[dict] = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        typ0 = (f.get("type") or "").lower()
        lab = label_of(f)
        name = f.get("name") or ""
        # 简道云 linkquery「客户类别」→ 只读展示，选客户后回填（须在 SKIP_TYPES 之前）
        if typ0 == "linkquery" and (lab or "").strip() == "客户类别":
            out.append({
                "id": "customer_category",
                "type": "text",
                "label": "客户类别",
                "form_editable": False,
                "available_on_create": True,
                "fill_stage": "initiator",
                "jdy_widget": name or None,
            })
            continue
        if typ0 in SKIP_TYPES:
            continue
        if not lab or not should_keep_field(lab, name):
            continue
        slug = _slug_for(lab, used)
        if slug == "serial_no" or lab in ("流程编号", "流水号") or typ0 == "sn":
            out.append(_serial_field(serial_prefix, name, digits=serial_digits, label=serial_label))
            continue
        typ = map_type(typ0)
        if typ0 == "linkfield":
            typ = "text"
        if typ0 == "address":
            typ = "address"
        if typ0 == "image":
            typ = "image"
        if typ0 == "sn":
            continue
        opts = options_of(f)
        if typ == "select" and not opts:
            typ = "text"
        # 客户 / 合同选择器
        if slug == "customer_name" or lab in ("客户名称", "公司名称", "单位名称"):
            typ = "customer"
            opts = []
        if slug in ("contract_no", "drawing_no") or lab in ("合同号", "合同编号", "图纸编号"):
            # 关联合同：统一 contract 类型（按图纸编号检索展示）
            typ = "contract"
            opts = []
            slug = "contract_no" if slug != "contract_no" else slug
            # ensure unique if drawing_no also present
            if slug in used and lab == "图纸编号":
                slug = "drawing_no_ref"
                used.add(slug)
            lab = "合同号" if typ == "contract" and lab == "图纸编号" else lab

        fd: dict = {"id": slug, "type": typ, "label": lab}
        if typ == "customer":
            fd["description"] = "从客户管理中选择。"
        if typ == "contract":
            fd["label"] = "合同号"
            fd["description"] = "从合同管理中选择；按图纸编号搜索，选项以图纸编号显示。"
        if name in req or f.get("required"):
            fd["required"] = True
        if opts and typ in ("select", "radio", "checkbox"):
            fd["options"] = opts
        if typ == "detail_table":
            cols = sub_columns(f, used, req)
            if cols:
                fd["detail_table_columns"] = cols
            else:
                continue
        if name:
            fd["jdy_widget"] = name
        if typ in ("person", "person_multi"):
            apply_pickable_scope(fd, jdy_field=f)
        if typ in ("person", "department") and slug in ("applicant", "department", "sales_person"):
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
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")
        elif typ == "datetime":
            _apply_datetime_date_only_props(fd, f)
        out.append(fd)

    # ensure serial exists
    if not any(f.get("id") == "serial_no" for f in out):
        out.insert(0, _serial_field(serial_prefix, digits=serial_digits, label=serial_label))
    return out


def unwrap_wf(raw: dict) -> dict:
    if isinstance(raw, dict) and "workflow_config" in raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def apply_cs_product_return_initiator_defaults(fields: list[dict], notes: list[str]) -> None:
    """提交人/发起部门：发起时默认当前用户及其主部门（对齐简道云）。"""
    for fd in fields:
        fid = fd.get("id")
        if fid == "field":
            props = dict(fd.get("props") or {})
            props["default_current_user"] = True
            fd["props"] = props
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")
        elif fid == "field_2":
            props = dict(fd.get("props") or {})
            props["default_current_dept"] = True
            fd["props"] = props
            fd.setdefault("available_on_create", True)
            fd.setdefault("fill_stage", "initiator")
    notes.append("提交人/发起部门：发起默认当前用户及主部门")


def apply_cs_product_return_warehouse_judge_policy(fields: list[dict], notes: list[str]) -> None:
    """明细「仓库判定*」：发起不可见/不可填，仓库/物流审批节点填写（简道云 optAuth 发起列不含此 widget）。"""
    for fd in fields:
        if fd.get("id") != "field_7":
            continue
        for col in fd.get("detail_table_columns") or []:
            if col.get("id") != "field_14" and col.get("jdy_widget") != "_widget_1665817650935":
                continue
            col["available_on_create"] = False
            col["fill_stage"] = "approver"
            col["required"] = True
    notes.append("明细「仓库判定*」：仅审批节点可填（发起不展示）")


def apply_cs_product_replace_fault_class_policy(fields: list[dict], notes: list[str]) -> None:
    """换货明细「故障分类」：简道云发起 optAuth 未授权，客服补登节点填写。"""
    for fd in fields:
        if fd.get("id") != "field_12":
            continue
        for col in fd.get("detail_table_columns") or []:
            if col.get("id") != "field_19" and col.get("jdy_widget") != "_widget_1617691334516":
                continue
            col["available_on_create"] = False
            col["fill_stage"] = "approver"
            col["required"] = True
    notes.append("换货明细「故障分类」：仅客服补登可填（发起不展示）")


def gen_one(key: str, title: str, entry: str, app: str, meta: dict) -> dict:
    fields_file = OUT / f"_jdy_{key}_fields.json"
    wf_file = OUT / f"_jdy_{key}_workflows_raw.json"
    if not fields_file.exists():
        raise FileNotFoundError(fields_file)
    fields_raw = json.loads(fields_file.read_text(encoding="utf-8"))
    wf_raw = {}
    if wf_file.exists():
        wf_raw = unwrap_wf(json.loads(wf_file.read_text(encoding="utf-8")))
    required_widgets = load_required_widgets(key)
    fields = build_fields(
        fields_raw,
        meta["serial_prefix"],
        required_widgets,
        serial_digits=int(meta.get("serial_digits") or 3),
        serial_label=meta.get("serial_label"),
    )
    # 不再人工硬加必填：以简道云 allowBlank===false 为准（经 optAuth 再拆到发起/审批）
    notes: list[str] = []
    if key == "cs_product_return":
        apply_cs_product_return_initiator_defaults(fields, notes)
        apply_cs_product_return_warehouse_judge_policy(fields, notes)
    if key == "cs_product_replace":
        apply_cs_product_replace_fault_class_policy(fields, notes)

    nodes, routes, notes_flow = build_flow(wf_raw, fields, title)
    notes.extend(notes_flow)
    linkage = load_linkage_pack(key)
    rules = build_rule_definitions(linkage, fields) if linkage else []
    if required_widgets:
        notes.append(
            f"edit_raw allowBlank=false：{len(required_widgets)} 个必填 widget"
        )
    if rules:
        notes.append(f"fieldShowRules → {len(rules)} 条显隐/条件必填规则")
    pack = {
        "name": meta["title"],
        "field_definitions": fields,
        "rule_definitions": rules,
        "flow_nodes": nodes,
        "flow_routes": routes,
        "notes": notes,
        "jdy_app": app,
        "jdy_entry": entry,
        "route": meta["route"],
    }

    n_req = sum(1 for f in fields if f.get("required"))
    n_req_cols = sum(
        1 for f in fields for c in (f.get("detail_table_columns") or []) if c.get("required")
    )
    md = [
        f"# {meta['title']} — CRM 字段对照",
        "",
        f"> 简道云 app=`{app}` entry=`{entry}`",
        "",
        f"- **builtin key**: `{key}`",
        f"- **路由**: `{meta['route']}`",
        f"- **字段数**: {len(fields)}（发起必填 {n_req}；明细列必填 {n_req_cols}）",
        f"- **流程节点**: {len(nodes)} / 连线 {len(routes)}",
        f"- **流水号前缀**: `{meta['serial_prefix']}`",
        f"- **必填来源**: `_jdy_customer_service_linkages.json`（edit allowBlank=false）",
        "",
        "| slug | 标签 | type | 必填 | 创建可填 | stage | jdy_widget |",
        "|------|------|------|------|----------|-------|------------|",
    ]
    for fd in fields:
        md.append(
            f"| {fd['id']} | {fd['label']} | {fd['type']} | "
            f"{'是' if fd.get('required') else ''} | "
            f"{'' if fd.get('available_on_create') is False else '是'} | "
            f"{fd.get('fill_stage') or ''} | `{fd.get('jdy_widget', '')}` |"
        )
        for col in fd.get("detail_table_columns") or []:
            md.append(
                f"| └ {col['id']} | {col['label']} | {col['type']} | "
                f"{'是' if col.get('required') else ''} | "
                f"| | `{col.get('jdy_widget', '')}` |"
            )
    md += ["", "### 流程降级备注", ""]
    for n in notes:
        md.append(f"- {n}")
    md.append("")
    (OUT / f"_jdy_{key}_crm_forms.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(
        f"{key}: fields={len(fields)} required={n_req}+cols{n_req_cols} "
        f"nodes={len(nodes)} routes={len(routes)}"
    )
    return pack


def main() -> None:
    matched = json.loads(MATCHED.read_text(encoding="utf-8")) if MATCHED.exists() else {}
    result: dict = {}
    for key, meta in FORMS_META.items():
        m = matched.get(key) or {}
        title = m.get("name") or meta["title"]
        entry = m.get("id") or ""
        app = m.get("app") or "58e2fbc7ffd1608b4ce92809"
        if not entry:
            raise SystemExit(f"missing entry for {key}; run entries pull first")
        result[key] = gen_one(key, title, entry, app, meta)

    GEN.write_text(
        "# -*- coding: utf-8 -*\n"
        "\"\"\"Auto-generated from docs/product/_jdy_cs_* dumps. Do not edit by hand.\"\"\"\n"
        "from __future__ import annotations\n"
        "import json\n\n"
        f"CUSTOMER_SERVICE_JDY = json.loads(r'''{json.dumps(result, ensure_ascii=False)}''')\n",
        encoding="utf-8",
    )
    print("wrote", GEN)


if __name__ == "__main__":
    main()
