# -*- coding: utf-8 -*-
"""本地：ensure 图纸/方案管理并检查设计人 pickable_scope。"""
from __future__ import annotations

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:8005"


def login(c: httpx.Client) -> dict:
    for user, pwd in (
        ("admin", "123456"),
        ("admin", "admin123"),
        ("001", "123456"),
        ("001", "admin123"),
    ):
        r = c.post("/api/v1/auth/login", json={"username": user, "password": pwd})
        body = r.json()
        if r.status_code == 200 and body.get("code") == 0:
            print("login ok:", user)
            return {"Authorization": f"Bearer {body['data']['access_token']}"}
    print("login failed", file=sys.stderr)
    sys.exit(1)


def show_scope(label: str, fields: list) -> None:
    print(f"--- {label} ---")
    for fid in ("designer", "design_assignees"):
        fd = next((x for x in fields if isinstance(x, dict) and x.get("id") == fid), None)
        scope = (fd.get("props") or {}).get("pickable_scope") if fd else "MISSING"
        print(fid, json.dumps(scope, ensure_ascii=False))


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=120)
    h = login(c)
    for key in ("drawing_requisition", "scheme_management"):
        print(f"\n===== {key} ensure =====")
        tpl = c.post(f"/api/v1/lc/builtin-templates/{key}/ensure", headers=h).json()
        if tpl.get("code") != 0:
            print("ensure fail", json.dumps(tpl, ensure_ascii=False)[:800])
            continue
        tid = tpl["data"]["id"]
        ver = tpl["data"].get("current_version")
        print("template", tid, "version", ver)
        design = c.get(f"/api/v1/lc/form-templates/{tid}/design", headers=h).json()["data"]
        show_scope(f"{key} design (latest)", design.get("field_definitions") or [])
        pub = c.get(f"/api/v1/lc/form-templates/{tid}/versions", headers=h).json()["data"]
        published = next((v for v in pub if v.get("status") == "published"), None)
        if published:
            show_scope(
                f"{key} published v{published.get('version_number')}",
                published.get("field_definitions") or [],
            )


if __name__ == "__main__":
    main()
