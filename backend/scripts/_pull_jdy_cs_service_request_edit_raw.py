# -*- coding: utf-8 -*-
"""Pull JDY edit raw for 客户服务申请及反馈 → allowBlank / showRules."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = "58e2fbc7ffd1608b4ce92809"
ENTRY = "5e06c8a92675f1000634baf1"
KEY = "cs_service_request"
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
        return {k: sanitize(v) for k, v in obj.items() if not SECRET_KEY_RE.search(str(k))}
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    return obj


def extract_required(content: dict) -> list[dict]:
    required = []
    seen = set()

    def scan(items, parent: str | None = None):
        for it in items or []:
            if not isinstance(it, dict):
                continue
            w = it.get("widget")
            if isinstance(w, dict):
                wid = w.get("widgetName")
                if w.get("allowBlank") is False and wid and wid not in seen:
                    seen.add(wid)
                    required.append({
                        "widget": wid,
                        "label": it.get("label") or wid,
                        "type": w.get("type"),
                        "parent": parent,
                        "allowBlank": False,
                    })
                if w.get("type") == "subform":
                    sub = w.get("items") or []
                    if sub and isinstance(sub[0], dict) and "widget" in sub[0]:
                        scan(sub, wid)
            for nk in ("items", "widgets"):
                nested = it.get(nk)
                if (
                    isinstance(nested, list)
                    and nested
                    and isinstance(nested[0], dict)
                    and "widget" in nested[0]
                ):
                    scan(nested, parent)

    scan(content.get("items") or [])
    return required


def main():
    api_key = load_api_key()
    token = pick_wrapper(api_key)
    url = f"{JDY_BASE}/_/admin/app/{APP}/form/{ENTRY}/edit"
    print("POST", url)
    r = requests.post(url, headers=jdy_headers(token), json={}, timeout=90)
    print("status", r.status_code, "len", len(r.text))
    r.raise_for_status()
    edit_raw = sanitize(r.json())
    raw_path = OUT / f"_jdy_{KEY}_edit_raw.json"
    raw_path.write_text(json.dumps(edit_raw, ensure_ascii=False, indent=2), encoding="utf-8")

    content = edit_raw.get("data") or edit_raw.get("content") or edit_raw
    if isinstance(content, dict) and "items" not in content:
        # sometimes nested under data.content
        content = content.get("content") or content
    required = extract_required(content if isinstance(content, dict) else {})
    link = {
        "forms": {
            KEY: {
                "app": APP,
                "entry": ENTRY,
                "required_fields": [
                    {"widget": r["widget"], "label": r["label"], "allowBlank": False, "parent": r.get("parent")}
                    for r in required
                ],
                "required_fields_detail": required,
            }
        }
    }
    link_path = OUT / "_jdy_customer_service_linkages.json"
    # merge if exists
    if link_path.exists():
        old = json.loads(link_path.read_text(encoding="utf-8"))
        forms = old.setdefault("forms", {})
        forms[KEY] = link["forms"][KEY]
        link = old
    link_path.write_text(json.dumps(link, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {raw_path}")
    print(f"wrote {link_path} required={len(required)}")
    for r in required:
        print(f"  [{r.get('parent') or '-'}] {r['label']} ({r['widget']}) type={r.get('type')}")


if __name__ == "__main__":
    main()
