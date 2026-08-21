# -*- coding: utf-8 -*-
"""从简道云/jdy-wrapper 拉取九流程业务角色成员。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FALLBACK_KEY = "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
WRAPPER_BASES = ["http://192.168.0.6:8015", "http://192.168.0.6:8011"]

ROLES = {
    # 客服内勤（更换/退回/函件/延期反馈备案）
    "64f2a247187194000af416be": ("cs_office", "230902客服内勤"),
    "62e9bfe0527ea90008320fab": ("cs_office", "7.1.2售出产品更换（补发）流程-客服补登"),
    "5f6c3e539a4cbe0006b74d65": ("cs_office", "7.5客户服务延期申请-客服反馈"),
    # 延期客服审批
    "5f6c3e74bb221e00067d4f39": ("cs_delay_approve", "7.5客户服务延期申请-客服审批"),
    # 发货
    "5f69a16377e34d0006f13047": ("ship_sales_outbound", "24.1发货通知流程-销售出库"),
    "66889a1cdc970f6d8b318231": ("gate_guard", "240706门岗保卫组"),
    # 生产卡 / 法务
    "5f55d129a526650006b36c22": ("prod_material_code", "1.2.8生产卡/补充流程-物料编码"),
    "5f69a45077e34d0006f136dd": ("legal", "24.2.3合同/项目评审-法务审批多人"),
    "5f69a976fbf7110006288375": ("legal", "法务办理"),
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
    raise SystemExit("No jdy-wrapper")


def fetch_users_by_role(base: str, api_key: str) -> dict[str, list[dict]]:
    by_role: dict[str, list[dict]] = {rid: [] for rid in ROLES}
    skip = 0
    while True:
        r = requests.get(
            f"{base}/api/sync/users",
            headers={"X-API-Key": api_key},
            params={"skip": skip, "limit": 100},
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or data.get("data") or []
        if isinstance(items, dict):
            items = items.get("items") or items.get("data") or []
        if not items:
            break
        for u in items:
            for role in u.get("roles") or []:
                rid = str(role.get("role_id") or role.get("_id") or role.get("id") or "")
                if rid not in by_role:
                    continue
                by_role[rid].append({
                    "username": u.get("username"),
                    "name": u.get("nickname") or u.get("name") or u.get("real_name"),
                    "status": u.get("status"),
                })
        skip += len(items)
        total = int(data.get("total") or 0)
        if total and skip >= total:
            break
        if len(items) < 100 and not total:
            break
    return by_role


def main() -> None:
    api_key = load_api_key()
    base = pick_wrapper(api_key)
    print("wrapper", base)
    by_role = fetch_users_by_role(base, api_key)
    out = {"wrapper": base, "roles": {}}
    for rid, (code, rname) in ROLES.items():
        members = by_role.get(rid) or []
        # dedupe by username
        seen = set()
        uniq = []
        for m in members:
            u = m.get("username")
            if not u or u in seen:
                continue
            seen.add(u)
            uniq.append(m)
        out["roles"][rid] = {"crm_code": code, "name": rname, "members": uniq}
        print(f"\n=== {rname} ({code}) n={len(uniq)} ===")
        if not uniq:
            print("  (简道云无成员 / 同步用户未挂此角色)")
        for m in uniq:
            print(f"  {m.get('name')}  username={m.get('username')}")
    path = ROOT / "docs" / "product" / "_jdy_nine_flow_role_members.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", path)


if __name__ == "__main__":
    main()
