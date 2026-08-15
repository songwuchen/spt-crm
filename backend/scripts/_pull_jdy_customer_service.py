# -*- coding: utf-8 -*-
"""Pull 客户服务部 6 张流程 fields + workflow into docs/product."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path

API_KEY = (
    os.environ.get("JDY_WRAPPER_API_KEY")
    or os.environ.get("FORM_API_KEY")
    or "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
)
BASE = os.environ.get("JDY_WRAPPER_BASE_URL", "http://192.168.0.6:8015").rstrip("/")
OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
MATCHED = OUT / "_jdy_customer_service_matched.json"

# fallback if matched file missing
FORMS_FALLBACK = [
    ("cs_service_request", "客户服务申请及反馈", "58e2fbc7ffd1608b4ce92809", "5e06c8a92675f1000634baf1"),
    ("cs_product_replace", "售出产品更换（补发）流程", "58e2fbc7ffd1608b4ce92809", "5e06f4ad2a9eb70007f7c164"),
    ("cs_product_return", "售出产品/工具退回流程SCCP/GJTH", "58e2fbc7ffd1608b4ce92809", "5e10538c0d5a270006df2763"),
    ("cs_loan_slip", "客服借据", "58e2fbc7ffd1608b4ce92809", "62cccb4c8ee15d0009136487"),
    ("cs_drawing_request", "客服领图", "58e2fbc7ffd1608b4ce92809", "63840316a3241c000a805869"),
    ("cs_service_delay", "客户服务延期申请", "58e2fbc7ffd1608b4ce92809", "5f9b6dacb6ec680007f9c46f"),
    ("cs_correspondence", "客服往来函件KFWLHJ", "58e2fbc7ffd1608b4ce92809", "65de94717b566a9ff2059102"),
]


def get_json(url: str):
    req = urllib.request.Request(
        url, headers={"X-API-Key": API_KEY, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


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
        widgets = f.get("widgets") or f.get("fields") or []
        if widgets:
            rows.extend(flatten_fields(widgets, name))
        elif typ in ("subform",) and items and isinstance(items[0], dict) and items[0].get("name"):
            rows.extend(flatten_fields(items, name))
    return rows


def summarize_flow(wf: dict | None, title: str) -> str:
    lines = [f"# 简道云「{title}」流程配置摘要", ""]
    if not wf:
        lines.append("**未取到 workflow_config**")
        return "\n".join(lines)
    flows = wf.get("flows") or []
    lines += [f"- 节点数: **{len(flows)}**", "", "## 节点列表", ""]
    type_c: Counter[str] = Counter()
    for i, f in enumerate(flows):
        if not isinstance(f, dict):
            continue
        typ = str(f.get("type") or "")
        type_c[typ] += 1
        lines.append(f"- {i}. `{f.get('flowId') or f.get('_id')}` {f.get('name')} ({typ or '-'})")
    lines += ["", "## 节点类型统计", ""]
    for t, c in type_c.most_common():
        lines.append(f"- `{t or '(空)'}`: {c}")
    return "\n".join(lines)


def forms_list() -> list[tuple[str, str, str, str]]:
    if MATCHED.exists():
        data = json.loads(MATCHED.read_text(encoding="utf-8"))
        out = []
        for key, m in data.items():
            out.append((key, m["name"], m["app"], m["id"]))
        return out
    return FORMS_FALLBACK


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    for key, title, app, eid in forms_list():
        print(f"\n======== {title} {eid} ========")
        fields_resp = get_json(f"{BASE}/api/form/{app}/{eid}/fields")
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
        print(f"fields={len(flat)}")

        try:
            cfg = get_json(f"{BASE}/api/data-hub/forms/{app}/{eid}/configs")
        except Exception as e:
            print("configs fail", e)
            cfg = {}
        (OUT / f"_jdy_{key}_workflows_raw.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        wf = None
        if isinstance(cfg, dict):
            wf = cfg.get("workflow_config")
            if wf is None and isinstance(cfg.get("data"), dict):
                wf = cfg["data"].get("workflow_config")
        (OUT / f"_jdy_{key}_flow_nodes.md").write_text(
            summarize_flow(wf if isinstance(wf, dict) else None, title),
            encoding="utf-8",
        )
        n_flow = len((wf or {}).get("flows") or []) if isinstance(wf, dict) else 0

        md = [
            f"# {title}（字段对照）",
            "",
            f"> 简道云 app=`{app}` entry=`{eid}`。CRM key=`{key}`。",
            f"> 流程节点数: **{n_flow}**；扁平字段: **{len(flat)}**。",
            "",
            "| name | title | type | required | parent |",
            "|------|-------|------|----------|--------|",
        ]
        for r in flat:
            md.append(
                f"| `{r.get('name','')}` | {r.get('title','')} | {r.get('type','')} | "
                f"{'是' if r.get('required') else ''} | `{r.get('parent') or ''}` |"
            )
        (OUT / f"_jdy_{key}_forms.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        print(f"flow_nodes={n_flow}")

    print("\nDONE")


if __name__ == "__main__":
    main()
