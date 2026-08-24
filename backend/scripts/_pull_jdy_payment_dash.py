# -*- coding: utf-8 -*-
"""Pull JDY 合同管理「收款登记仪表盘」dash_config."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = "56ca77ce1efc301d279b8a4d"
DASH = "6217260b07289c00071aeca4"
FORM = "5d63721786b06824f3fcc07f"
API_KEY = (
    os.environ.get("JDY_WRAPPER_API_KEY")
    or os.environ.get("FORM_API_KEY")
    or "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
)
WRAPPER_BASES = ["http://192.168.0.6:8015", "http://192.168.0.6:8011"]
JDY = "https://www.jiandaoyun.com"
OUT = Path(__file__).resolve().parents[2] / "docs" / "product"


def pick_wrapper() -> tuple[str, dict]:
    for base in WRAPPER_BASES:
        try:
            r = requests.get(f"{base}/api/token/", headers={"X-API-Key": API_KEY}, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json().get("data") or {}
            if all(data.get(k) for k in ("csrf", "sid", "csrf_token")):
                return base, data
        except Exception:
            continue
    raise RuntimeError("No JDY wrapper token")


def jdy_headers(token: dict) -> dict:
    return {
        "Cookie": f"_csrf={token['csrf']}; JDY_SID={token['sid']}",
        "X-CSRF-Token": token["csrf_token"],
        "x-jdy-ver": "v1",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def main() -> None:
    base, token = pick_wrapper()
    print("wrapper", base)
    endpoints = [
        (f"{JDY}/_/admin/app/{APP}/entry/{DASH}/dash_config", "dash_config"),
        (f"{JDY}/_/admin/app/{APP}/entry/{DASH}/get", "dash_get"),
        (f"{JDY}/_/admin/app/{APP}/dash/{DASH}/config", "dash_config2"),
        (f"{JDY}/_/admin/app/{APP}/dash/{DASH}/edit", "dash_edit"),
        (f"{JDY}/_/admin/app/{APP}/entry/{DASH}/edit", "entry_edit"),
        (f"{JDY}/_/admin/app/{APP}/form/{DASH}/edit", "form_dash_edit"),
        (f"{JDY}/_/admin/app/{APP}/form/{FORM}/edit", "form_edit"),
    ]
    for url, label in endpoints:
        r = requests.post(url, headers=jdy_headers(token), json={}, timeout=90)
        print("POST", label, r.status_code)
        if r.status_code != 200:
            print(r.text[:300])
            continue
        data = r.json()
        out = OUT / f"_jdy_payment_registration_{label}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2)[:3_000_000], encoding="utf-8")
        print("wrote", out.name, "top", list(data.keys())[:8] if isinstance(data, dict) else type(data))

    for path in (
        f"/api/data-hub/forms/{APP}/{DASH}/configs",
        f"/api/data-hub/forms/{APP}/{FORM}/configs",
    ):
        r = requests.get(f"{base}{path}", headers={"X-API-Key": API_KEY}, timeout=60)
        print("GET", path, r.status_code)
        if r.status_code == 200:
            out = OUT / f"_jdy_payment_registration_{path.split('/')[-2]}.json"
            out.write_text(json.dumps(r.json(), ensure_ascii=False, indent=2)[:3_000_000], encoding="utf-8")
            print("wrote", out.name)


if __name__ == "__main__":
    main()
