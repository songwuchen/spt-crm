# -*- coding: utf-8 -*-
"""Pull JDY drawing form edit raw configs + extract required/visibility."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP_ID = "5e6c73fefc53170006bd4e9c"
FORMS = [
    {
        "key": "requisition",
        "name": "领用",
        "entry_id": "5e6ee08be3051400062159ee",
        "raw_path": Path(r"G:/ruolin-a/spt-crm/docs/product/_jdy_drawing_requisition_edit_raw.json"),
    },
    {
        "key": "install_notice",
        "name": "安装图",
        "entry_id": "5e6edc5b44b7070006d191cb",
        "raw_path": Path(r"G:/ruolin-a/spt-crm/docs/product/_jdy_install_drawing_notice_edit_raw.json"),
    },
]
OUT_JSON = Path(r"G:/ruolin-a/spt-crm/docs/product/_jdy_drawing_forms_linkages.json")
OUT_MD = Path(r"G:/ruolin-a/spt-crm/docs/product/_jdy_drawing_forms_linkages.md")

WRAPPER_BASES = ["http://192.168.0.6:8015", "http://192.168.0.6:8011"]
JDY_BASE = "https://www.jiandaoyun.com"
FALLBACK_KEY = "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"

SECRET_KEY_RE = re.compile(
    r"(cookie|csrf|token|sid|password|secret|authorization|api[_-]?key|session)",
    re.I,
)


def load_api_key() -> Tuple[str, str]:
    """Return (key, source_desc). Never print the key."""
    for p in [
        Path(r"G:/ruolin-a/jdy-wrapper/.env"),
        Path(r"G:/ruolin-a/spt-crm/backend/.env"),
    ]:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in ("JDY_WRAPPER_API_KEY", "FORM_API_KEY") and v:
                return v, f"{p.name}:{k}"
    return FALLBACK_KEY, "fallback_prior"


def pick_wrapper(api_key: str) -> Tuple[str, Dict[str, str]]:
    errors = []
    for base in WRAPPER_BASES:
        try:
            r = requests.get(
                f"{base}/api/token/",
                headers={"X-API-Key": api_key},
                timeout=15,
            )
            if r.status_code != 200:
                errors.append(f"{base} status={r.status_code}")
                continue
            body = r.json()
            data = body.get("data") if isinstance(body, dict) else None
            if not isinstance(data, dict):
                errors.append(f"{base} unexpected token payload keys")
                continue
            need = ("csrf", "sid", "csrf_token")
            if not all(data.get(k) for k in need):
                errors.append(f"{base} token missing fields")
                continue
            # sanitize token copy for return (only needed fields)
            token = {k: data[k] for k in need}
            return base, token
        except Exception as e:
            errors.append(f"{base} err={type(e).__name__}")
    raise RuntimeError("No wrapper token: " + "; ".join(errors))


def jdy_headers(token: Dict[str, str]) -> Dict[str, str]:
    return {
        "Cookie": f"_csrf={token['csrf']}; JDY_SID={token['sid']}",
        "X-CSRF-Token": token["csrf_token"],
        "x-jdy-ver": "v1",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "spt-crm-jdy-pull/1.0",
    }


def fetch_edit(app_id: str, entry_id: str, token: Dict[str, str]) -> Dict[str, Any]:
    url = f"{JDY_BASE}/_/admin/app/{app_id}/form/{entry_id}/edit"
    r = requests.post(url, headers=jdy_headers(token), json={}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"edit HTTP {r.status_code} body_len={len(r.text)}")
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"edit non-json: {e} body_len={len(r.text)}")


def sanitize(obj: Any) -> Any:
    """Drop secret-looking keys recursively; keep form config."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if SECRET_KEY_RE.search(str(k)):
                continue
            out[k] = sanitize(v)
        return out
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    return obj


def walk_items(items: List[Dict[str, Any]], label_map: Dict[str, str], widgets: List[Dict[str, Any]]):
    for it in items or []:
        if not isinstance(it, dict):
            continue
        w = it.get("widget")
        label = it.get("label")
        if isinstance(w, dict):
            wid = w.get("widgetName")
            if wid and isinstance(label, str):
                label_map[wid] = label
            widgets.append({"label": label, "widget": w})
            # subform nested items
            if w.get("type") == "subform":
                sub_items = w.get("items") or []
                # subform items may be same structure
                if sub_items and isinstance(sub_items[0], dict) and "widget" in sub_items[0]:
                    walk_items(sub_items, label_map, widgets)
                else:
                    # sometimes subform widgets listed differently
                    for sw in sub_items:
                        if isinstance(sw, dict) and sw.get("widgetName"):
                            widgets.append({"label": sw.get("label"), "widget": sw})
                            if sw.get("label"):
                                label_map[sw["widgetName"]] = sw["label"]
        # nested containers
        for nk in ("items", "widgets", "tabs"):
            nested = it.get(nk)
            if isinstance(nested, list) and nested and isinstance(nested[0], dict) and "widget" in nested[0]:
                walk_items(nested, label_map, widgets)


def build_label_map(content: Dict[str, Any]) -> Dict[str, str]:
    label_map: Dict[str, str] = {}
    widgets: List[Dict[str, Any]] = []
    walk_items(content.get("items") or [], label_map, widgets)
    return label_map


def extract_required(content: Dict[str, Any], label_map: Dict[str, str]) -> List[Dict[str, Any]]:
    required = []
    seen = set()

    def scan_item_list(items):
        for it in items or []:
            if not isinstance(it, dict):
                continue
            w = it.get("widget")
            if isinstance(w, dict):
                if w.get("allowBlank") is False:
                    wid = w.get("widgetName")
                    if wid and wid not in seen:
                        seen.add(wid)
                        required.append(
                            {
                                "widget": wid,
                                "label": it.get("label") or label_map.get(wid) or wid,
                                "allowBlank": False,
                                "type": w.get("type"),
                            }
                        )
                if w.get("type") == "subform":
                    sub = w.get("items") or []
                    if sub and isinstance(sub[0], dict) and "widget" in sub[0]:
                        scan_item_list(sub)
            for nk in ("items", "widgets"):
                nested = it.get(nk)
                if isinstance(nested, list) and nested and isinstance(nested[0], dict) and "widget" in nested[0]:
                    scan_item_list(nested)

    scan_item_list(content.get("items") or [])
    return required


def extract_field_show_rules(content: Dict[str, Any], label_map: Dict[str, str]) -> List[Dict[str, Any]]:
    rules = content.get("fieldShowRules") or []
    out = []
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        filt = rule.get("filter") or {}
        conds = []
        for c in filt.get("cond") or []:
            if not isinstance(c, dict):
                continue
            field = c.get("field")
            conds.append(
                {
                    "trigger_widget": field,
                    "trigger_label": label_map.get(field, field),
                    "method": c.get("method"),
                    "value": c.get("value"),
                    "type": c.get("type"),
                    "mode": c.get("mode"),
                }
            )
        show_fields = []
        for f in rule.get("fields") or []:
            show_fields.append({"widget": f, "label": label_map.get(f, f)})
        out.append(
            {
                "scope": "form",
                "index": idx,
                "rel": filt.get("rel"),
                "conditions": conds,
                "show_fields": show_fields,
                "raw": rule,
            }
        )
    return out


def extract_subform_show_rules(content: Dict[str, Any], label_map: Dict[str, str]) -> List[Dict[str, Any]]:
    raw = content.get("subformFieldShowRules") or {}
    out = []
    if isinstance(raw, dict):
        for sub_wid, rules in raw.items():
            for idx, rule in enumerate(rules or []):
                if not isinstance(rule, dict):
                    continue
                filt = rule.get("filter") or {}
                conds = []
                for c in filt.get("cond") or []:
                    if not isinstance(c, dict):
                        continue
                    field = c.get("field")
                    conds.append(
                        {
                            "trigger_widget": field,
                            "trigger_label": label_map.get(field, field),
                            "method": c.get("method"),
                            "value": c.get("value"),
                        }
                    )
                show_fields = []
                for f in rule.get("fields") or []:
                    show_fields.append({"widget": f, "label": label_map.get(f, f)})
                out.append(
                    {
                        "scope": "subform",
                        "subform_widget": sub_wid,
                        "subform_label": label_map.get(sub_wid, sub_wid),
                        "index": idx,
                        "rel": filt.get("rel"),
                        "conditions": conds,
                        "show_fields": show_fields,
                        "raw": rule,
                    }
                )
    elif isinstance(raw, list):
        for idx, rule in enumerate(raw):
            out.append({"scope": "subform", "index": idx, "raw": rule})
    return out


def extract_option_widgets_map(content: Dict[str, Any], label_map: Dict[str, str]) -> List[Dict[str, Any]]:
    out = []

    def scan_items(items):
        for it in items or []:
            if not isinstance(it, dict):
                continue
            w = it.get("widget")
            if isinstance(w, dict):
                wid = w.get("widgetName")
                for opt in w.get("items") or []:
                    if not isinstance(opt, dict):
                        continue
                    wm = opt.get("widgetsMap")
                    if wm:
                        targets = []
                        for tw in wm:
                            targets.append({"widget": tw, "label": label_map.get(tw, tw)})
                        out.append(
                            {
                                "widget": wid,
                                "label": it.get("label") or label_map.get(wid, wid),
                                "option": opt.get("value") if opt.get("value") is not None else opt.get("text"),
                                "show_widgets": targets,
                            }
                        )
                if w.get("type") == "subform":
                    sub = w.get("items") or []
                    if sub and isinstance(sub[0], dict) and "widget" in sub[0]:
                        scan_items(sub)
            for nk in ("items", "widgets"):
                nested = it.get(nk)
                if isinstance(nested, list) and nested and isinstance(nested[0], dict) and "widget" in nested[0]:
                    scan_items(nested)

    scan_items(content.get("items") or [])
    return out


def fmt_cond(conds: List[Dict[str, Any]]) -> str:
    parts = []
    for c in conds:
        lab = c.get("trigger_label") or c.get("trigger_widget")
        wid = c.get("trigger_widget")
        method = c.get("method")
        val = c.get("value")
        parts.append(f"{lab} (`{wid}`) {method} {json.dumps(val, ensure_ascii=False)}")
    return "；".join(parts) if parts else "-"


def fmt_targets(fields: List[Dict[str, Any]]) -> str:
    parts = []
    for f in fields:
        parts.append(f"{f.get('label')} (`{f.get('widget')}`)")
    return "；".join(parts) if parts else "-"


def main():
    errors: List[str] = []
    api_key, key_src = load_api_key()
    print(f"api_key_source={key_src} len={len(api_key)}")

    try:
        wrapper_base, token = pick_wrapper(api_key)
        print(f"wrapper_ok={wrapper_base} token_fields=ok")
    except Exception as e:
        print(f"FATAL wrapper: {e}")
        sys.exit(1)

    forms_out: Dict[str, Any] = {}
    summary_rows = []

    for form in FORMS:
        entry_id = form["entry_id"]
        print(f"\n=== Fetch {form['name']} {entry_id} ===")
        try:
            raw = fetch_edit(APP_ID, entry_id, token)
        except Exception as e:
            msg = f"{form['key']}: fetch failed: {e}"
            print(msg)
            errors.append(msg)
            continue

        # unwrap if nested under data
        if isinstance(raw, dict) and "content" not in raw and isinstance(raw.get("data"), dict):
            raw = raw["data"]

        sanitized = sanitize(raw)
        # keep core form meta; drop nothing else of value
        form["raw_path"].parent.mkdir(parents=True, exist_ok=True)
        form["raw_path"].write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {form['raw_path']} bytes={form['raw_path'].stat().st_size}")

        content = sanitized.get("content") or {}
        name = sanitized.get("name") or form["name"]
        label_map = build_label_map(content)
        required = extract_required(content, label_map)
        show_rules = extract_field_show_rules(content, label_map)
        sub_rules = extract_subform_show_rules(content, label_map)
        opt_map = extract_option_widgets_map(content, label_map)

        forms_out[form["key"]] = {
            "source": {
                "app_id": APP_ID,
                "entry_id": entry_id,
                "name": name,
                "note": "来自简道云 POST /_/admin/app/.../form/.../edit 原始配置；wrapper GET /api/form/.../fields 仅返回格式化 fields，会丢掉 fieldShowRules/allowBlank 细节",
                "wrapper_raw_endpoint": None,
                "fetched_via": f"wrapper {wrapper_base}/api/token + 直连 jiandaoyun edit",
                "raw_file": form["raw_path"].name,
            },
            "required_fields": [{"widget": r["widget"], "label": r["label"], "allowBlank": r["allowBlank"]} for r in required],
            "required_fields_detail": required,
            "fieldShowRules": show_rules,
            "subformFieldShowRules": sub_rules,
            "widgetsMap_option_visibility": opt_map,
            "counts": {
                "required_fields": len(required),
                "fieldShowRules": len(show_rules),
                "subformFieldShowRules": len(sub_rules),
                "widgetsMap_option_visibility": len(opt_map),
                "label_map": len(label_map),
            },
        }
        summary_rows.append(forms_out[form["key"]])
        print(
            f"counts required={len(required)} showRules={len(show_rules)} "
            f"subShow={len(sub_rules)} optMap={len(opt_map)}"
        )

    payload = {
        "app_id": APP_ID,
        "app_name": "通用流程",
        "fetched_via": f"wrapper /api/token + 直连 jiandaoyun edit",
        "forms": forms_out,
        "errors": errors,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT_JSON}")

    # Markdown
    lines = []
    lines.append("# 简道云图纸相关表单：必填与显隐联动摘录")
    lines.append("")
    lines.append(f"- 应用：`通用流程`（`{APP_ID}`）")
    lines.append("- 配置来源：简道云原始 `POST /_/admin/app/{app}/form/{entry}/edit`（经 jdy-wrapper `/api/token` 取会话后直连）")
    lines.append("- 说明：wrapper `GET /api/form/.../fields` **无 raw/edit 暴露**，格式化 fields 会丢掉 `fieldShowRules` / `allowBlank` 等")
    lines.append("- 原始 edit：`_jdy_drawing_requisition_edit_raw.json`、`_jdy_install_drawing_notice_edit_raw.json`")
    lines.append("- 结构化：`_jdy_drawing_forms_linkages.json`")
    lines.append("- 本文不包含任何 API Key / Cookie")
    lines.append("")

    for form in FORMS:
        fo = forms_out.get(form["key"])
        if not fo:
            lines.append(f"## {form['name']}（拉取失败）")
            lines.append("")
            continue
        src = fo["source"]
        counts = fo["counts"]
        lines.append(f"## {src['name']}（`{src['entry_id']}`）")
        lines.append("")
        lines.append(
            f"- 必填字段：**{counts['required_fields']}**；fieldShowRules：**{counts['fieldShowRules']}**；"
            f"subformFieldShowRules：**{counts['subformFieldShowRules']}**；"
            f"选项 widgetsMap：**{counts['widgetsMap_option_visibility']}**"
        )
        lines.append("")
        lines.append("### 必填字段（allowBlank===false）")
        lines.append("")
        lines.append("| # | 标签 | widget |")
        lines.append("|---|---|---|")
        for i, r in enumerate(fo["required_fields"]):
            lines.append(f"| {i} | {r['label']} | `{r['widget']}` |")
        if not fo["required_fields"]:
            lines.append("| — | （无） | — |")
        lines.append("")
        lines.append("### 字段显隐联动（fieldShowRules）")
        lines.append("")
        lines.append("| # | 触发条件 | 动作 | 目标字段 |")
        lines.append("|---|---|---|---|")
        for rule in fo["fieldShowRules"]:
            lines.append(
                f"| {rule['index']} | {fmt_cond(rule['conditions'])} | 显示 | {fmt_targets(rule['show_fields'])} |"
            )
        if not fo["fieldShowRules"]:
            lines.append("| — | （无） | — | — |")
        lines.append("")
        lines.append("### 子表显隐（subformFieldShowRules）")
        lines.append("")
        lines.append("| 子表 | # | 触发条件 | 动作 | 目标子字段 |")
        lines.append("|---|---|---|---|---|")
        for rule in fo["subformFieldShowRules"]:
            lines.append(
                f"| {rule.get('subform_label')} (`{rule.get('subform_widget')}`) | {rule.get('index')} | "
                f"{fmt_cond(rule.get('conditions') or [])} | 显示 | {fmt_targets(rule.get('show_fields') or [])} |"
            )
        if not fo["subformFieldShowRules"]:
            lines.append("| — | — | （无） | — | — |")
        lines.append("")
        lines.append("### 选项级 widgetsMap（选项可见性）")
        lines.append("")
        lines.append("| 触发字段 | 选项值 | 显示目标 |")
        lines.append("|---|---|---|")
        for opt in fo["widgetsMap_option_visibility"]:
            lines.append(
                f"| {opt['label']} (`{opt['widget']}`) | {opt['option']} | {fmt_targets(opt['show_widgets'])} |"
            )
        if not fo["widgetsMap_option_visibility"]:
            lines.append("| — | （无） | — |")
        lines.append("")

    if errors:
        lines.append("## 错误")
        lines.append("")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD}")

    # Final human summary (ASCII-safe counts first)
    print("\n======== SUMMARY ========")
    for form in FORMS:
        fo = forms_out.get(form["key"])
        if not fo:
            print(form["key"], "FAILED")
            continue
        c = fo["counts"]
        print(
            f"{form['key']}: name={fo['source']['name']} "
            f"required={c['required_fields']} showRules={c['fieldShowRules']} "
            f"subShow={c['subformFieldShowRules']} optMap={c['widgetsMap_option_visibility']}"
        )
        print("  required labels:")
        for r in fo["required_fields"]:
            print(f"    - {r['label']} ({r['widget']})")
        print("  show rules:")
        for rule in fo["fieldShowRules"]:
            trig = fmt_cond(rule["conditions"])
            tgt = fmt_targets(rule["show_fields"])
            print(f"    - [{rule['index']}] {trig} -> {tgt}")
    if errors:
        print("ERRORS:", errors)


if __name__ == "__main__":
    main()
