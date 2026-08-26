#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull 简道云「合同技术协议评审 HTJSXY」打印模板 layout。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = "5de0b3e85600ec0006f420f2"
ENTRY = "6464383b8541ae000863cbda"
PRINT_ID = "20230517112920525"
PRINT_NAME = "合同技术协议评审"
JDY = "https://www.jiandaoyun.com"
WRAPPER_BASES = ["http://192.168.0.6:8015", "http://192.168.0.6:8011"]
FALLBACK_KEY = "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
OUT = Path(__file__).resolve().parents[2] / "docs" / "product"


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


def pick_wrapper(api_key: str) -> tuple[str, dict]:
    errors: list[str] = []
    for base in WRAPPER_BASES:
        try:
            r = requests.get(f"{base}/api/token/", headers={"X-API-Key": api_key}, timeout=15)
            if r.status_code != 200:
                errors.append(f"{base} status={r.status_code}")
                continue
            data = r.json().get("data") or {}
            if all(data.get(k) for k in ("csrf", "sid", "csrf_token")):
                return base, {k: data[k] for k in ("csrf", "sid", "csrf_token")}
            errors.append(f"{base} token missing fields")
        except Exception as e:
            errors.append(f"{base} {type(e).__name__}")
    raise RuntimeError("No wrapper token: " + "; ".join(errors))


def jdy_headers(token: dict) -> dict:
    return {
        "Cookie": f"_csrf={token['csrf']}; JDY_SID={token['sid']}",
        "X-CSRF-Token": token["csrf_token"],
        "x-jdy-ver": "v1",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "spt-crm-jdy-pull/1.0",
    }


def pull_print(entry: str, pid: str, hdr: dict) -> dict | None:
    paths = [
        f"/_/admin/app/{APP}/form/{entry}/print/{pid}/edit",
        f"/_/admin/app/{APP}/form/{entry}/print/{pid}",
        f"/_/admin/app/{APP}/print/{pid}/edit",
    ]
    for path in paths:
        url = JDY + path
        try:
            r = requests.post(url, headers=hdr, json={}, timeout=90)
        except Exception as e:
            print(f"  {path} err={e}")
            continue
        print(f"  {path} -> {r.status_code} len={len(r.content)}")
        if r.status_code == 200 and r.content:
            try:
                return r.json()
            except Exception:
                print("    not json")
    return None


def summarize_layout(data: dict) -> str:
    lines = [
        "# 合同技术协议评审 HTJSXY — 简道云打印模板",
        "",
        f"- app: `{APP}`（销售中心）",
        f"- entry: `{ENTRY}`",
        f"- print_id: `{PRINT_ID}`",
        f"- name: {PRINT_NAME}",
        f"- type: table",
        "",
        "## layout 摘要",
        "",
    ]
    layout = data.get("layout") or data.get("content") or data
    if isinstance(layout, dict):
        for k in ("title", "name", "type", "orientation", "paper", "margin", "rows", "cells", "items"):
            if k in layout:
                v = layout[k]
                if isinstance(v, (list, dict)) and len(str(v)) > 500:
                    lines.append(f"- **{k}**: ({type(v).__name__}, len={len(v)})")
                else:
                    lines.append(f"- **{k}**: `{v}`")
    elif isinstance(layout, list):
        lines.append(f"- layout list len={len(layout)}")
    lines.append("")
    lines.append("## 顶层 keys")
    lines.append("")
    lines.append(", ".join(f"`{k}`" for k in data.keys()))
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    base, token = pick_wrapper(api_key)
    print("wrapper", base)
    hdr = jdy_headers(token)

    data = pull_print(ENTRY, PRINT_ID, hdr)
    if not data:
        print("FAILED to pull print template")
        sys.exit(1)

    json_out = OUT / f"_jdy_tech_agreement_review_print_{PRINT_ID}.json"
    json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", json_out)

    md_out = OUT / "_jdy_tech_agreement_review_print_templates.md"
    md_out.write_text(summarize_layout(data), encoding="utf-8")
    print("saved", md_out)
    print("keys", list(data.keys())[:20])


if __name__ == "__main__":
    main()
