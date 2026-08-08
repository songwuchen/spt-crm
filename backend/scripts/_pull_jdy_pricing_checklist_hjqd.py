# -*- coding: utf-8 -*-
"""Pull 简道云「中央研究院 / 研究院统计 / 核价清单 / 核价清单传递流程HJQD」字段+流程+edit raw。"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = "584658417562f37a227fa805"  # 中央研究院
ENTRY = "667638539c1f73c42e4bcbff"  # 核价清单传递流程HJQD (entryId)
KEY_NAME = "pricing_checklist_hjqd"
TITLE = "核价清单传递流程HJQD"
MENU_PATH = "中央研究院 / 研究院统计 / 核价清单 / 核价清单传递流程HJQD"

OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
WRAPPER_BASES = ["http://192.168.0.6:8015", "http://192.168.0.6:8011"]
JDY_BASE = "https://www.jiandaoyun.com"
FALLBACK_KEY = "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
SECRET_KEY_RE = re.compile(
    r"(cookie|csrf|token|sid|password|secret|authorization|api[_-]?key|session)",
    re.I,
)


def load_api_key() -> str:
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
            if k.strip() in ("JDY_WRAPPER_API_KEY", "FORM_API_KEY") and v.strip():
                return v.strip().strip('"').strip("'")
    return FALLBACK_KEY


def pick_wrapper(api_key: str) -> tuple[str, dict]:
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
                errors.append(f"{base} bad token payload")
                continue
            need = ("csrf", "sid", "csrf_token")
            if not all(data.get(k) for k in need):
                errors.append(f"{base} token missing fields")
                continue
            return base, {k: data[k] for k in need}
        except Exception as e:
            errors.append(f"{base} {type(e).__name__}")
    raise RuntimeError("No wrapper token: " + "; ".join(errors))


def get_json(base: str, api_key: str, path: str) -> Any:
    r = requests.get(
        f"{base}{path}",
        headers={"X-API-Key": api_key, "Accept": "application/json"},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()


def jdy_headers(token: dict) -> dict:
    return {
        "Cookie": f"_csrf={token['csrf']}; JDY_SID={token['sid']}",
        "X-CSRF-Token": token["csrf_token"],
        "x-jdy-ver": "v1",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "spt-crm-jdy-pull/1.0",
    }


def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items() if not SECRET_KEY_RE.search(str(k))}
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    return obj


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
            "options": [o for o in opts if o is not None][:40],
        })
        widgets = f.get("widgets") or f.get("fields") or []
        if widgets:
            rows.extend(flatten_fields(widgets, name))
        elif typ in ("subform",) and items and isinstance(items[0], dict) and (
            items[0].get("name") or items[0].get("type")
        ):
            rows.extend(flatten_fields(items, name))
    return rows


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
        f"> 菜单：{MENU_PATH}",
        f"> app=`{APP}` entry=`{ENTRY}`",
        "> 来源：jdy-wrapper data-hub configs → workflow_config。",
        "",
    ]
    if not wf:
        lines.append("**未取到 workflow_config**")
        return "\n".join(lines)
    flows = wf.get("flows") or []
    lines += [
        f"- editable: `{wf.get('editable')}`",
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
        extras = []
        for k in ("approveType", "approvalMethod", "ruleType", "condition", "chains"):
            if f.get(k) not in (None, "", [], {}):
                v = f[k]
                extras.append(f"{k}={'ok' if isinstance(v, (dict, list)) else v}")
        if isinstance(f.get("optAuth"), dict):
            extras.append("有字段权限")
        if extras:
            summary = (summary + "; " + ", ".join(extras)).strip("; ")
        lines.append(f"| {i} | {fid} | {name} | {typ or '-'} | {summary} |")
    lines += ["", "## 节点类型统计", ""]
    for t, c in type_c.most_common():
        lines.append(f"- `{t or '(空)'}`: {c}")
    return "\n".join(lines)


def extract_fields_list(fields_resp: Any) -> list:
    fields_data = fields_resp.get("data", fields_resp) if isinstance(fields_resp, dict) else fields_resp
    if isinstance(fields_data, dict):
        return fields_data.get("fields") or fields_data.get("widgets") or []
    return fields_data if isinstance(fields_data, list) else []


def extract_wf(cfg: Any) -> dict | None:
    if not isinstance(cfg, dict):
        return None
    wf = cfg.get("workflow_config")
    if wf is None:
        data = cfg.get("data") or {}
        if isinstance(data, dict):
            wf = data.get("workflow_config")
    return wf if isinstance(wf, dict) else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    base, token = pick_wrapper(api_key)
    print(f"wrapper={base} app={APP} entry={ENTRY}")

    print("1) fields …")
    fields_resp = get_json(base, api_key, f"/api/form/{APP}/{ENTRY}/fields")
    (OUT / f"_jdy_{KEY_NAME}_fields.json").write_text(
        json.dumps(fields_resp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = extract_fields_list(fields_resp)
    flat = flatten_fields(fields)
    (OUT / f"_jdy_{KEY_NAME}_fields_flat.json").write_text(
        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   fields raw={len(fields)} flat={len(flat)}")

    print("2) workflow configs …")
    try:
        cfg = get_json(base, api_key, f"/api/data-hub/forms/{APP}/{ENTRY}/configs")
    except Exception as e:
        print(f"   configs fail: {e}", file=sys.stderr)
        cfg = {}
    (OUT / f"_jdy_{KEY_NAME}_workflows_raw.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    wf = extract_wf(cfg)
    n_flow = len((wf or {}).get("flows") or []) if isinstance(wf, dict) else 0
    (OUT / f"_jdy_{KEY_NAME}_flow_nodes.md").write_text(
        summarize_flow(wf, TITLE), encoding="utf-8"
    )
    print(f"   flow_nodes={n_flow}")

    print("3) edit raw …")
    url = f"{JDY_BASE}/_/admin/app/{APP}/form/{ENTRY}/edit"
    r = requests.post(url, headers=jdy_headers(token), json={}, timeout=90)
    if r.status_code != 200:
        # try _id alternate
        alt = "667638539c1f73c42e4bcc00"
        print(f"   edit HTTP {r.status_code}, retry entry={alt}")
        url = f"{JDY_BASE}/_/admin/app/{APP}/form/{alt}/edit"
        r = requests.post(url, headers=jdy_headers(token), json={}, timeout=90)
    r.raise_for_status()
    edit_raw = sanitize(r.json())
    (OUT / f"_jdy_{KEY_NAME}_edit_raw.json").write_text(
        json.dumps(edit_raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   edit_raw keys={list(edit_raw.keys())[:12] if isinstance(edit_raw, dict) else type(edit_raw)}")

    md = [
        f"# {TITLE}",
        "",
        f"> 菜单：`{MENU_PATH}`",
        f"> 简道云 app=`{APP}` entry=`{ENTRY}`",
        f"> 流程节点数: **{n_flow}**；扁平字段: **{len(flat)}**。",
        "",
        "## 产出文件",
        "",
        f"- `_jdy_{KEY_NAME}_fields.json` — 字段原始",
        f"- `_jdy_{KEY_NAME}_fields_flat.json` — 扁平字段",
        f"- `_jdy_{KEY_NAME}_workflows_raw.json` — 流程/配置原始",
        f"- `_jdy_{KEY_NAME}_flow_nodes.md` — 流程节点摘要",
        f"- `_jdy_{KEY_NAME}_edit_raw.json` — 表单 edit 原始（已去密钥字段）",
        "",
        "## 字段一览",
        "",
        "| name | title | type | required | parent |",
        "|------|-------|------|----------|--------|",
    ]
    for row in flat:
        md.append(
            f"| `{row.get('name','')}` | {row.get('title','')} | {row.get('type','')} | "
            f"{'是' if row.get('required') else ''} | `{row.get('parent') or ''}` |"
        )
    (OUT / f"_jdy_{KEY_NAME}_forms.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"done -> {OUT / ('_jdy_' + KEY_NAME + '_*')}")


if __name__ == "__main__":
    main()
