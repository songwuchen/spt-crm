# -*- coding: utf-8 -*-
"""Pull JDY edit raw for 合同评审 → showFields (数据管理列表列)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = "5de0b3e85600ec0006f420f2"
ENTRY = "5de0b58e8edfae0006cb571a"
KEY = "contract_review"
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


def pick_wrapper(api_key: str) -> dict:
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
            if not isinstance(data, dict) or not all(data.get(k) for k in ("csrf", "sid", "csrf_token")):
                errors.append(f"{base} bad token")
                continue
            return {k: data[k] for k in ("csrf", "sid", "csrf_token")}
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
    token = pick_wrapper(api_key)
    url = f"{JDY_BASE}/_/admin/app/{APP}/form/{ENTRY}/edit"
    r = requests.post(url, headers=jdy_headers(token), json={}, timeout=60)
    r.raise_for_status()
    edit_raw = sanitize(r.json())
    raw_path = OUT / f"_jdy_{KEY}_edit_raw.json"
    raw_path.write_text(json.dumps(edit_raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", raw_path)

    content = edit_raw.get("data") or edit_raw.get("content") or edit_raw
    if not isinstance(content, dict):
        print("no content dict")
        return
    show = content.get("showFields") or []
    meta = content.get("showFieldsMeta") or {}
    # field widgets map
    widgets = {}
    for w in content.get("widgets") or content.get("items") or []:
        if isinstance(w, dict) and w.get("widgetName"):
            widgets[w["widgetName"]] = w.get("label") or w.get("title") or w.get("widgetName")
        # nested
        for sub in (w.get("items") or []) if isinstance(w, dict) else []:
            if isinstance(sub, dict) and sub.get("widgetName"):
                widgets[sub["widgetName"]] = sub.get("label") or sub.get("title") or sub["widgetName"]

    print("showFields count", len(show))
    for wid in show:
        print(f"  {wid}  {widgets.get(wid) or meta.get(wid) or ''}")

    # also dump flow state related if present
    for k in ("hasFlow", "flow", "name", "title"):
        if k in content:
            print(k, content.get(k) if k != "flow" else "(present)")


if __name__ == "__main__":
    main()
