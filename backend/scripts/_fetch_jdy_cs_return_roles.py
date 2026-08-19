#!/usr/bin/env python3
"""Fetch JDY role members for cs_product_return approver roles."""
from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
FALLBACK_KEY = "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
WRAPPER_BASES = ["http://192.168.0.6:8015", "http://192.168.0.6:8011"]

ROLES = {
    "64f2a247187194000af416be": "230902客服内勤",
}


def load_api_key() -> str:
    for p in (Path(r"G:/ruolin-a/jdy-wrapper/.env"), ROOT / "backend" / ".env"):
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


def pick_wrapper(api_key: str) -> str:
    for base in WRAPPER_BASES:
        try:
            r = requests.get(f"{base}/api/token/", headers={"X-API-Key": api_key}, timeout=15)
            if r.status_code == 200:
                return base
        except Exception:
            continue
    raise RuntimeError("No jdy-wrapper available")


def fetch_users_by_role(base: str, api_key: str) -> dict[str, list[dict]]:
    by_role: dict[str, list[dict]] = {rid: [] for rid in ROLES}
    skip = 0
    while True:
        r = requests.get(
            f"{base}/api/sync/users",
            headers={"X-API-Key": api_key},
            params={"skip": skip, "limit": 100},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or []
        if not items:
            break
        for u in items:
            for role in u.get("roles") or []:
                rid = str(role.get("role_id") or role.get("_id") or "")
                # role_id in sync may be numeric; match by _id in ROLES keys
                for key in ROLES:
                    if rid == key or str(role.get("_id") or "") == key:
                        by_role[key].append({
                            "username": u.get("username"),
                            "name": u.get("nickname") or u.get("name"),
                        })
        skip += len(items)
        total = int(data.get("total") or skip)
        if skip >= total:
            break
    return by_role


def main() -> None:
    api_key = load_api_key()
    base = pick_wrapper(api_key)
    by_role = fetch_users_by_role(base, api_key)
    out = {"wrapper": base, "roles": {}}
    for rid, rname in ROLES.items():
        members = by_role.get(rid) or []
        out["roles"][rid] = {"name": rname, "members": members}
        usernames = [m["username"] for m in members if m.get("username")]
        print(rname, "->", members)
        if usernames:
            print("  specified_user:", usernames if len(usernames) > 1 else usernames[0])
    out_path = ROOT / "docs" / "product" / "_jdy_cs_return_role_members.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out_path)


if __name__ == "__main__":
    main()
