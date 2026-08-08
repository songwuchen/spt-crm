"""Pull JDY「核价管理流程」fields + workflow into docs/product (quote_management)."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

KEY = (
    os.environ.get("JDY_WRAPPER_API_KEY")
    or os.environ.get("FORM_API_KEY")
    or "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
)
BASE = os.environ.get("JDY_WRAPPER_BASE_URL", "http://192.168.0.6:8015").rstrip("/")
OUT = Path(__file__).resolve().parents[2] / "docs" / "product"

APP = "5e6c73fefc53170006bd4e9c"  # 通用流程
ENTRY = "5e6c740e6d74970006a67190"  # 核价管理流程
KEY_NAME = "quote_management"
TITLE = "核价管理流程"


def get_json(url: str) -> dict:
    import urllib.request

    req = urllib.request.Request(
        url, headers={"X-API-Key": KEY, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
        "> 来源：jdy-wrapper data-hub configs → workflow_config。产品名 CRM 侧为「报价管理」。",
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
        widgets = f.get("widgets") or f.get("fields") or []
        if widgets:
            rows.extend(flatten_fields(widgets, name))
        elif typ in ("subform",) and items and isinstance(items[0], dict) and items[0].get("name"):
            rows.extend(flatten_fields(items, name))
    return rows


def main() -> None:
    if not KEY:
        raise SystemExit("Set JDY_WRAPPER_API_KEY or FORM_API_KEY")
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"pull fields {APP}/{ENTRY} …")
    fields_resp = get_json(f"{BASE}/api/form/{APP}/{ENTRY}/fields")
    (OUT / f"_jdy_{KEY_NAME}_fields.json").write_text(
        json.dumps(fields_resp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields_data = fields_resp.get("data", fields_resp) if isinstance(fields_resp, dict) else fields_resp
    if isinstance(fields_data, dict):
        fields = fields_data.get("fields") or fields_data.get("widgets") or []
    else:
        fields = fields_data if isinstance(fields_data, list) else []
    flat = flatten_fields(fields)
    (OUT / f"_jdy_{KEY_NAME}_fields_flat.json").write_text(
        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"fields raw={len(fields)} flat={len(flat)}")

    print("pull configs / workflow …")
    try:
        cfg = get_json(f"{BASE}/api/data-hub/forms/{APP}/{ENTRY}/configs")
    except Exception as e:
        print(f"configs fail: {e}", file=sys.stderr)
        cfg = {}
    (OUT / f"_jdy_{KEY_NAME}_workflows_raw.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    wf = cfg.get("workflow_config") if isinstance(cfg, dict) else None
    if wf is None and isinstance(cfg, dict):
        data = cfg.get("data") or {}
        if isinstance(data, dict):
            wf = data.get("workflow_config")
    (OUT / f"_jdy_{KEY_NAME}_flow_nodes.md").write_text(
        summarize_flow(wf if isinstance(wf, dict) else None, TITLE),
        encoding="utf-8",
    )
    n_flow = len((wf or {}).get("flows") or []) if isinstance(wf, dict) else 0

    md = [
        "# 核价管理流程 → 报价管理（字段对照）",
        "",
        f"> 简道云 app=`{APP}` entry=`{ENTRY}`（通用流程 / 核价管理流程）。",
        f"> CRM builtin code: `{KEY_NAME}`，展示名：报价管理。",
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
    (OUT / f"_jdy_{KEY_NAME}_forms.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"done fields={len(flat)} flow_nodes={n_flow} -> {OUT}")


if __name__ == "__main__":
    main()
