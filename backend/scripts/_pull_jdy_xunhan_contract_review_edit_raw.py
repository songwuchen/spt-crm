#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull edit_raw for 销售中心「迅焊公司合同评审」."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = "5de0b3e85600ec0006f420f2"
ENTRY = "67d3d515c8df85cc24de064f"
KEY = "xunhan_contract_review"
OUT = Path(__file__).resolve().parents[2] / "docs" / "product"
WRAPPER_BASE = "http://192.168.0.6:8015"
JDY_BASE = "https://www.jiandaoyun.com"
FALLBACK_KEY = "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
SECRET_KEY_RE = re.compile(
    r"(cookie|csrf|token|sid|password|secret|authorization|api[_-]?key|session)",
    re.I,
)


def load_api_key() -> str:
    for p in [
        Path(r"G:/ruolin-a/jdy-wrapper/.env"),
        Path(__file__).resolve().parents[1] / ".env",
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


def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("***" if SECRET_KEY_RE.search(str(k) or "") else sanitize(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    return obj


def main() -> None:
    api_key = load_api_key()
    r = requests.get(
        f"{WRAPPER_BASE}/api/token/",
        headers={"X-API-Key": api_key},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()["data"]
    headers = {
        "Cookie": f"_csrf={data['csrf']}; JDY_SID={data['sid']}",
        "X-CSRF-Token": data["csrf_token"],
        "x-jdy-ver": "v1",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{JDY_BASE}/_/admin/app/{APP}/form/{ENTRY}/edit"
    r2 = requests.post(url, headers=headers, json={}, timeout=120)
    print("edit status", r2.status_code)
    r2.raise_for_status()
    edit_raw = sanitize(r2.json())
    out_path = OUT / f"_jdy_{KEY}_edit_raw.json"
    out_path.write_text(json.dumps(edit_raw, ensure_ascii=False, indent=2), encoding="utf-8")
    content = edit_raw.get("data") or edit_raw.get("content") or edit_raw
    attr = content.get("attr") or {}
    link = attr.get("linkage") or content.get("linkage") or {}
    fsr = link.get("fieldShowRules") or content.get("fieldShowRules") or []
    ssr = link.get("subformFieldShowRules") or content.get("subformFieldShowRules") or []
    print(f"saved {out_path.name}")
    print("fieldShowRules", len(fsr), "subformFieldShowRules", len(ssr))
    # sn rules
    items = (content.get("content") or content).get("items") if isinstance(content, dict) else None
    if not items and isinstance(content, dict):
        items = content.get("items")
    for it in items or []:
        w = (it or {}).get("widget") or {}
        if w.get("type") == "sn" or (it or {}).get("label") == "流水号":
            print("sn rules", json.dumps(w.get("rules"), ensure_ascii=False)[:300])
            break


if __name__ == "__main__":
    main()
