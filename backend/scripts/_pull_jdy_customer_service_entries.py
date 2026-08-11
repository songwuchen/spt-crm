# -*- coding: utf-8 -*-
"""Match 6 CS forms from JDY entryMap (reuse drawing walk_entries)."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pull_jdy_drawing_forms import walk_entries  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
APP = "58e2fbc7ffd1608b4ce92809"
GENERAL = "5e6c73fefc53170006bd4e9c"
API_KEY = (
    os.environ.get("JDY_WRAPPER_API_KEY")
    or os.environ.get("FORM_API_KEY")
    or "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
)
BASE = os.environ.get("JDY_WRAPPER_BASE_URL", "http://192.168.0.6:8015").rstrip("/")

TARGETS = {
    "cs_service_request": ["客户服务申请及反馈"],
    "cs_product_replace": ["售出产品更换", "更换（补发）", "更换(补发)"],
    "cs_product_return": ["售出产品/工具退回", "SCCP", "GJTH", "工具退回"],
    "cs_loan_slip": ["客服借据"],
    "cs_service_delay": ["客户服务延期申请", "服务延期申请"],
    "cs_correspondence": ["客服往来函件", "KFWLHJ", "往来函件"],
}


def get_json(url: str) -> dict | list:
    req = urllib.request.Request(
        url, headers={"X-API-Key": API_KEY, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_flat(app: str) -> list[dict]:
    raw = get_json(f"{BASE}/api/app/{app}/entries")
    payload = raw.get("data", raw) if isinstance(raw, dict) else raw
    flat = walk_entries(payload)
    for e in flat:
        e["app"] = app
    return flat


def is_dead(name: str) -> bool:
    return any(x in name for x in ("删关", "停用", "已取消", "-关", "关停", "210406关"))


def pick(flat: list[dict], aliases: list[str]) -> dict | None:
    cands = []
    for e in flat:
        name = e.get("name") or ""
        if not name:
            continue
        if not any(a in name for a in aliases):
            continue
        cands.append(e)
    # prefer live forms
    live = [e for e in cands if not is_dead(e["name"])]
    pool = live or cands
    if not pool:
        return None
    # prefer exact-ish shorter names / flow forms
    pool.sort(key=lambda e: (0 if e.get("hasFlow") else 1, len(e["name"])))
    return pool[0]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    flat = load_flat(APP) + load_flat(GENERAL)
    (OUT / "_jdy_customer_service_entries_all.json").write_text(
        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("total entries", len(flat))

    interesting = []
    for e in flat:
        n = e.get("name") or ""
        if any(
            k in n
            for k in (
                "客服", "售后", "借据", "退回", "更换", "补发", "函件",
                "延期", "SCCP", "GJTH", "KFWLHJ", "服务申请", "服务记录",
            )
        ):
            interesting.append(e)
            print(f"  {e['id']} | {n} | flow={e.get('hasFlow')} | {e.get('folder')}")

    matched = {}
    for key, aliases in TARGETS.items():
        hit = pick(flat, aliases)
        if hit:
            matched[key] = {
                "id": hit["id"],
                "name": hit["name"],
                "app": hit["app"],
                "hasFlow": hit.get("hasFlow"),
                "folder": hit.get("folder"),
            }
            print(f"MATCH {key} -> {hit['name']} / {hit['id']}")
        else:
            print(f"MISS {key}")

    # known fallback
    matched.setdefault(
        "cs_service_request",
        {
            "id": "5e06c8a92675f1000634baf1",
            "name": "客户服务申请及反馈",
            "app": APP,
            "hasFlow": True,
        },
    )

    lines = [
        "# 客户服务部 → CRM 售后低代码入口对照",
        "",
        f"> 客户服务部 app=`{APP}`；通用流程 app=`{GENERAL}`。",
        "",
        "| CRM key | 简道云名称 | entry | app | hasFlow |",
        "|---------|------------|-------|-----|---------|",
    ]
    for key in TARGETS:
        m = matched.get(key)
        if not m:
            lines.append(f"| `{key}` | （未匹配） | — | — | — |")
            continue
        lines.append(
            f"| `{key}` | {m['name']} | `{m['id']}` | `{m['app']}` | {m.get('hasFlow')} |"
        )
    lines += ["", "## 相关入口一览", ""]
    for e in interesting:
        lines.append(
            f"- `{e['id']}` {e['name']} （app=`{e['app']}` flow={e.get('hasFlow')}）"
        )

    (OUT / "_jdy_customer_service_entries.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    (OUT / "_jdy_customer_service_matched.json").write_text(
        json.dumps(matched, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    missing = [k for k in TARGETS if k not in matched]
    print("wrote entries md; missing=", missing)
    if missing:
        sys.exit(2)


if __name__ == "__main__":
    main()
