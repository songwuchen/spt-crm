#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull 简道云「合同评审」打印模板（仅 system 系统打印）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = "5de0b3e85600ec0006f420f2"
ENTRY = "5de0b58e8edfae0006cb571a"
PRINT_ID = "system"
PRINT_NAME = "系统打印"
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    base, token = pick_wrapper(api_key)
    print("wrapper", base)
    hdr = jdy_headers(token)
    data = pull_print(ENTRY, PRINT_ID, hdr)
    raw_out = OUT / "_jdy_contract_review_print_raw.json"
    if data:
        raw_out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("WROTE", raw_out)
    else:
        print("FAILED to pull print template")
        sys.exit(1)

    edit = json.loads((OUT / "_jdy_contract_review_edit_raw.json").read_text(encoding="utf-8"))
    md_lines = [
        "# 合同评审 — 简道云打印模板对照",
        "",
        f"- app: `{APP}`（销售中心）",
        f"- entry: `{ENTRY}`",
        f"- 表单名: {edit.get('name', '')}",
        "",
        "## printList",
        "",
    ]
    for p in edit.get("printList") or []:
        md_lines.append(f"- `{p.get('id')}` — {p.get('name')}")
    md_lines.extend([
        "",
        "> 与技术协议 HTJSXY 不同：合同评审**没有**自定义 table 打印模板，仅有「系统打印」。",
        "> CRM 按系统打印惯例：表格字段 + 审批意见区。",
        "",
        "## layout API 顶层 keys",
        "",
        ", ".join(f"`{k}`" for k in (data or {}).keys()),
        "",
    ])
    md_out = OUT / "_jdy_contract_review_print_templates.md"
    md_out.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print("WROTE", md_out)


if __name__ == "__main__":
    main()
