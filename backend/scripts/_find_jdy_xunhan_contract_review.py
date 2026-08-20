#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find 迅焊公司合同评审 entry in 销售中心 app."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pull_jdy_drawing_forms import walk_entries  # noqa: E402
import urllib.request

API_KEY = (
    os.environ.get("JDY_WRAPPER_API_KEY")
    or os.environ.get("FORM_API_KEY")
    or "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
)
BASE = os.environ.get("JDY_WRAPPER_BASE_URL", "http://192.168.0.6:8015").rstrip("/")
APP = "5de0b3e85600ec0006f420f2"  # 销售中心
OUT = Path(__file__).resolve().parents[2] / "docs" / "product"


def get_json(url: str):
    req = urllib.request.Request(
        url, headers={"X-API-Key": API_KEY, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = get_json(f"{BASE}/api/app/{APP}/entries")
    payload = raw.get("data", raw) if isinstance(raw, dict) else raw
    flat = walk_entries(payload)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_jdy_sales_center_entries_all.json").write_text(
        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("total entries", len(flat))
    keys = ("迅焊", "合同评审", "小萌", "合同")
    hits = []
    for e in flat:
        name = e.get("name") or ""
        if any(k in name for k in keys):
            hits.append(e)
    hits.sort(key=lambda e: e.get("name") or "")
    print("hits", len(hits))
    for e in hits:
        print(
            f"- {e.get('name')} | id={e.get('id') or e.get('entryId')} | "
            f"type={e.get('type')} hasFlow={e.get('hasFlow')} parent={e.get('parentName')}"
        )


if __name__ == "__main__":
    main()
