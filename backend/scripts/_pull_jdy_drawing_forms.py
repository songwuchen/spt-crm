"""Pull 通用流程「图纸」两表 fields + workflow_config via jdy-wrapper."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

KEY = os.environ.get("JDY_WRAPPER_API_KEY") or os.environ.get("FORM_API_KEY") or ""
BASE = os.environ.get("JDY_WRAPPER_BASE_URL", "http://192.168.0.6:8015").rstrip("/")
APP = "5e6c73fefc53170006bd4e9c"  # 通用流程
OUT = Path(__file__).resolve().parents[2] / "docs" / "product"

TARGET_NAMES = {
    "drawing_requisition": ("合同图纸（资料）领用申请", "合同图纸", "领用申请"),
    "install_drawing_notice": ("安装图设计通知", "安装图"),
}


def get_json(url: str) -> dict | list:
    req = urllib.request.Request(
        url, headers={"X-API-Key": KEY, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def walk_entries(node, folder: str = "", acc: list | None = None) -> list:
    if acc is None:
        acc = []
    if node is None:
        return acc
    if isinstance(node, list):
        for n in node:
            walk_entries(n, folder, acc)
        return acc
    if not isinstance(node, dict):
        return acc

    # 通用流程 app 结构：{ entryList, entryMap }
    if "entryMap" in node and isinstance(node["entryMap"], dict):
        emap = node["entryMap"]
        # folder names: parents that only appear as group ids
        folder_names: dict[str, str] = {}
        for eid, meta in emap.items():
            if isinstance(meta, dict) and meta.get("type") in ("folder", "group", "directory"):
                folder_names[eid] = meta.get("name") or meta.get("text") or eid
        for eid, meta in emap.items():
            if not isinstance(meta, dict):
                continue
            name = meta.get("name") or meta.get("text") or ""
            typ = str(meta.get("type") or "")
            if typ in ("folder", "group", "directory"):
                continue
            parent = str(meta.get("parent") or "")
            acc.append({
                "folder": folder_names.get(parent, parent),
                "name": name,
                "type": typ,
                "id": meta.get("entryId") or eid,
                "hasFlow": meta.get("hasFlow"),
            })
        return acc

    name = node.get("name") or node.get("text") or node.get("title") or ""
    eid = node.get("_id") or node.get("entryId") or node.get("id") or ""
    typ = str(node.get("type") or node.get("entryType") or node.get("contentType") or "")
    for child_key in ("forms", "children", "entries", "items", "list", "entryList"):
        child = node.get(child_key)
        if isinstance(child, (list, dict)):
            walk_entries(child, name or folder, acc)
    if eid and name and not any(
        isinstance(node.get(k), (list, dict)) for k in ("forms", "children", "entries", "items", "list", "entryList", "entryMap")
    ):
        acc.append({"folder": folder, "name": name, "type": typ or "entry", "id": eid})
    return acc


def match_target(name: str, aliases: tuple[str, ...]) -> bool:
    n = name.replace(" ", "")
    return any(a.replace(" ", "") in n for a in aliases)


def cand_summary(cand) -> str:
    if not isinstance(cand, dict):
        return str(cand)[:80]
    parts = []
    for k in ("users", "departs", "departments", "roles", "managers", "dynamic"):
        v = cand.get(k)
        if v:
            parts.append(f"{k}:{len(v) if isinstance(v, list) else type(v).__name__}")
    return ", ".join(parts) if parts else json.dumps(cand, ensure_ascii=False)[:80]


def summarize_flow(wf: dict | None, title: str) -> str:
    lines = [
        f"# 简道云「{title}」流程配置摘要",
        "",
        "> 来源：jdy-wrapper data-hub configs → workflow_config。",
        "",
    ]
    if not wf:
        lines.append("**未取到 workflow_config**")
        return "\n".join(lines)
    flows = wf.get("flows") or []
    lines += [
        f"- 节点数: **{len(flows)}**",
        "",
        "## 节点列表",
        "",
        "| # | flowId | name | type | 审批人摘要 |",
        "|---|--------|------|------|------------|",
    ]
    type_c: Counter[str] = Counter()
    for i, f in enumerate(flows):
        if not isinstance(f, dict):
            continue
        fid = f.get("flowId", f.get("_id", ""))
        name = f.get("name", "")
        typ = str(f.get("type") or "")
        type_c[typ] += 1
        cand = f.get("candidates") or f.get("approvers") or f.get("chargers") or {}
        summary = cand_summary(cand if isinstance(cand, dict) else {"raw": cand})
        lines.append(f"| {i} | {fid} | {name} | {typ or '-'} | {summary} |")
    lines += ["", "## 节点类型统计", ""]
    for t, c in type_c.most_common():
        lines.append(f"- `{t or '(空)'}`: {c}")
    return "\n".join(lines)


def flatten_fields(fields: list, parent: str | None = None) -> list[dict]:
    rows = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        name = f.get("name") or f.get("widgetName") or ""
        title = f.get("title") or f.get("label") or f.get("text") or name
        typ = f.get("type") or f.get("widgetType") or ""
        required = bool(f.get("required") or (f.get("validate") or {}).get("required"))
        items = f.get("items") or f.get("options") or []
        opts = []
        for it in items:
            if isinstance(it, dict):
                opts.append(it.get("value") or it.get("text") or it.get("label"))
            else:
                opts.append(it)
        rows.append({
            "name": name,
            "title": title,
            "type": typ,
            "required": required,
            "parent": parent,
            "options": [o for o in opts if o is not None][:30],
        })
        sub = f.get("items") if typ in ("subform", "table", "detail_table") else None
        # some schemas nest widgets under items as field defs
        widgets = f.get("widgets") or f.get("fields") or []
        if widgets:
            rows.extend(flatten_fields(widgets, name))
        elif typ in ("subform",) and items and isinstance(items[0], dict) and items[0].get("name"):
            rows.extend(flatten_fields(items, name))
    return rows


def slugify(title: str, used: set[str]) -> str:
    mapping = {
        "申请人": "applicant", "申请日期": "apply_date", "申请部门": "department",
        "图纸编号": "drawing_no", "合同号": "contract_no", "合同编号": "contract_no",
        "单位名称": "customer_name", "公司名称": "customer_name", "客户名称": "customer_name",
        "资料类型": "material_type", "领用份数": "copies", "份数": "copies",
        "领用用途": "purpose", "用途": "purpose", "是否需归还": "need_return",
        "预计归还日期": "expected_return_date", "附件": "attachments", "备注": "remark",
        "通知人": "notifier", "通知日期": "notice_date", "项目名称": "project_name",
        "设计类型": "design_type", "紧急程度": "urgency", "要求完成日期": "require_date",
        "设计要求说明": "design_req", "设计要求": "design_req", "安装现场": "install_site",
        "相关附件": "attachments", "流水号": "serial_no", "提交人": "submitter",
        "提交时间": "submit_time", "当前节点": "current_node", "流程状态": "flow_status",
    }
    base = mapping.get(title)
    if not base:
        # pinyin-less fallback
        base = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower() or "field"
        if base[0].isdigit():
            base = "f_" + base
    slug = base
    i = 2
    while slug in used:
        slug = f"{base}_{i}"
        i += 1
    used.add(slug)
    return slug


def map_type(jdy_type: str) -> str:
    t = (jdy_type or "").lower()
    table = {
        "text": "text", "textarea": "textarea", "number": "number", "integer": "number",
        "datetime": "date", "date": "date", "radiogroup": "radio", "radio": "radio",
        "checkboxgroup": "checkbox", "checkbox": "checkbox", "combo": "select",
        "select": "select", "user": "person", "usergroup": "person", "dept": "department",
        "department": "department", "upload": "file", "image": "file", "file": "file",
        "subform": "detail_table", "table": "detail_table", "address": "text",
        "phone": "text", "sn": "text", "flowstate": "text", "richeditor": "textarea",
        "linkfield": "text", "linkquery": "text", "lookup": "text", "aggregation": "text",
        "ocr": "text", "signature": "file", "location": "text", "switch": "switch",
    }
    return table.get(t, "text")


def fields_to_builtin(flat: list[dict]) -> list[dict]:
    used: set[str] = set()
    skip_types = {"flowstate", "sn", "aggregation", "button", "separator", "pagebreak", "hint"}
    out = []
    for row in flat:
        if row.get("parent"):
            continue  # detail columns handled separately if needed
        typ = str(row.get("type") or "").lower()
        if typ in skip_types:
            continue
        title = str(row.get("title") or row.get("name") or "")
        if not title or title.startswith("_"):
            continue
        slug = slugify(title, used)
        fd: dict = {
            "id": slug,
            "type": map_type(typ),
            "label": title,
        }
        if row.get("required"):
            fd["required"] = True
        opts = row.get("options") or []
        if opts and fd["type"] in ("select", "radio", "checkbox"):
            fd["options"] = [{"label": str(o), "value": str(o)} for o in opts]
        if row.get("name"):
            fd["jdy_widget"] = row["name"]
        out.append(fd)
    return out


def main() -> None:
    if not KEY:
        raise SystemExit("Set JDY_WRAPPER_API_KEY or FORM_API_KEY")
    OUT.mkdir(parents=True, exist_ok=True)

    entries_raw = get_json(f"{BASE}/api/app/{APP}/entries")
    (OUT / "_jdy_general_flow_entries.json").write_text(
        json.dumps(entries_raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload = entries_raw.get("data", entries_raw) if isinstance(entries_raw, dict) else entries_raw
    flat_entries = walk_entries(payload)
    # also try if data itself is list of forms
    if not flat_entries and isinstance(payload, dict):
        for v in payload.values():
            walk_entries(v, "", flat_entries)
    (OUT / "_jdy_general_flow_entries_flat.json").write_text(
        json.dumps(flat_entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"entries flat: {len(flat_entries)}")
    for e in flat_entries:
        if any(k in e["name"] for k in ("图纸", "安装", "领用")):
            print(f"  - [{e.get('folder')}] {e['name']} id={e['id']} type={e.get('type')}")

    resolved: dict[str, dict] = {}
    for key, aliases in TARGET_NAMES.items():
        hit = next((e for e in flat_entries if match_target(e["name"], aliases)), None)
        if not hit:
            print(f"WARN: not found {key} aliases={aliases}")
            continue
        resolved[key] = hit
        print(f"OK {key} -> {hit['name']} / {hit['id']}")

    builtin_preview: dict[str, list] = {}
    md_lines = [
        "# 图纸通用流程表单字段对照",
        "",
        f"> 状态：**已从简道云 live 拉取**（app=`{APP}` 通用流程）。",
        f"> 来源：`GET /api/app/{{app}}/entries` + `/api/form/{{app}}/{{entry}}/fields` + data-hub configs。",
        "",
    ]

    for key, hit in resolved.items():
        entry_id = hit["id"]
        title = hit["name"]
        fields_resp = get_json(f"{BASE}/api/form/{APP}/{entry_id}/fields")
        (OUT / f"_jdy_{key}_fields.json").write_text(
            json.dumps(fields_resp, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        fields_data = fields_resp.get("data", fields_resp) if isinstance(fields_resp, dict) else fields_resp
        if isinstance(fields_data, dict):
            fields = fields_data.get("fields") or fields_data.get("widgets") or []
        else:
            fields = fields_data if isinstance(fields_data, list) else []
        flat = flatten_fields(fields)
        (OUT / f"_jdy_{key}_fields_flat.json").write_text(
            json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        try:
            cfg = get_json(f"{BASE}/api/data-hub/forms/{APP}/{entry_id}/configs")
        except Exception as e:
            print(f"configs fail {key}: {e}")
            cfg = {}
        (OUT / f"_jdy_{key}_workflows_raw.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        wf = cfg.get("workflow_config") if isinstance(cfg, dict) else None
        (OUT / f"_jdy_{key}_flow_nodes.md").write_text(
            summarize_flow(wf, title), encoding="utf-8"
        )

        builtin = fields_to_builtin(flat)
        builtin_preview[key] = builtin
        md_lines += [
            f"## {title}",
            "",
            f"- **builtin key / code**: `{key}`",
            f"- **app_id**: `{APP}`",
            f"- **entry_id**: `{entry_id}`",
            f"- **流程节点数**: {len((wf or {}).get('flows') or [])}",
            "",
            "| slug | 标签 | JDY type | CRM type | 必填 | widget |",
            "|------|------|----------|----------|------|--------|",
        ]
        for fd, row in zip(builtin, [r for r in flat if not r.get("parent")]):
            # re-find matching flat row by title
            pass
        # rebuild table from builtin + flat by title
        by_title = {str(r.get("title")): r for r in flat if not r.get("parent")}
        for fd in builtin:
            src = by_title.get(fd["label"], {})
            md_lines.append(
                f"| {fd['id']} | {fd['label']} | {src.get('type','')} | {fd['type']} | "
                f"{'是' if fd.get('required') else ''} | `{fd.get('jdy_widget','')}` |"
            )
        md_lines.append("")
        print(f"{key}: fields={len(flat)} builtin={len(builtin)} flow_nodes={len((wf or {}).get('flows') or [])}")

    (OUT / "_jdy_drawing_builtin_preview.json").write_text(
        json.dumps(builtin_preview, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "_jdy_drawing_forms.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print("done ->", OUT / "_jdy_drawing_forms.md")


if __name__ == "__main__":
    main()
