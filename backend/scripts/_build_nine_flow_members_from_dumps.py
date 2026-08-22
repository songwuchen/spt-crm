# -*- coding: utf-8 -*-
"""从已有 JDY dump / 生成物 / 历史办理人抽样汇总九流程角色成员。"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]

ROLE_META = {
    "cs_office": {
        "jdy_ids": ["64f2a247187194000af416be", "62e9bfe0527ea90008320fab", "5f6c3e539a4cbe0006b74d65"],
        "files": [
            "docs/product/_jdy_cs_return_role_members.json",
            "docs/product/_jdy_cs_replace_role_members.json",
        ],
    },
    "cs_delay_approve": {
        "jdy_ids": ["5f6c3e74bb221e00067d4f39"],
        "files": [],
    },
    "ship_sales_outbound": {
        "jdy_ids": ["5f69a16377e34d0006f13047"],
        "files": [],
        # 历史仓库办理人抽样（inventory / 退回流程仓库节点）
        "seed": [
            {"username": "02366368263850", "name": "司丹丹"},
            {"username": "01346931076927160185", "name": "段亚非"},
            {"username": "0654354430671114", "name": "侯静"},
        ],
    },
    "gate_guard": {
        "jdy_ids": ["66889a1cdc970f6d8b318231"],
        "files": [],
        "seed": [],
    },
    "prod_material_code": {
        "jdy_ids": ["5f55d129a526650006b36c22"],
        "files": [],
        "seed": [
            {"username": "02366236281651", "name": "韩青芳"},
            {"username": "010624465121410798", "name": "司子潆"},
            {"username": "45424060301188765", "name": "郭雪"},
        ],
    },
    "legal": {
        "jdy_ids": ["5f69a45077e34d0006f136dd", "5f69a976fbf7110006288375"],
        "files": [],
        "seed": [
            {"username": "543355140326074979", "name": "杜习慧"},
            {"username": "4723152427763414", "name": "孔雪"},
            {"username": "256932256424153873", "name": "张孟杰"},
        ],
    },
}


def load_file_members(path: Path, want_ids: set[str] | None = None) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    roles = data.get("roles") or {}
    if isinstance(roles, dict):
        for rid, info in roles.items():
            if want_ids is not None and str(rid) not in want_ids:
                continue
            for m in info.get("members") or []:
                out.append(m)
    elif isinstance(data.get("members"), list):
        out.extend(data["members"])
    return out


def sample_shipment_warehouse_from_raw():
    """从发货/退回 raw 中再挖仓库办理人 username。"""
    found = {}
    for p in ROOT.glob("docs/product/_jdy_*shipment*"):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, uname in re.findall(
            r'"name"\s*:\s*"(司丹丹|段亚非|侯静)".{0,80}?"username"\s*:\s*"(\d+)"', text, re.S
        ):
            found[uname] = name
        for uname, name in re.findall(
            r'"username"\s*:\s*"(\d+)".{0,80}?"name"\s*:\s*"(司丹丹|段亚非|侯静)"', text, re.S
        ):
            found[uname] = name
    return [{"username": u, "name": n} for u, n in found.items()]


def main():
    live = {}
    try:
        import requests
        key = "mRfnPFSgDj0YAkENsXBaew1UhZlZmgAc"
        base = "http://192.168.0.6:8015"
        r = requests.get(
            f"{base}/api/sync/users",
            headers={"X-API-Key": key},
            params={"skip": 0, "limit": 5},
            timeout=10,
        )
        live["status"] = r.status_code
        live["body"] = r.text[:200]
    except Exception as e:
        live["error"] = str(e)

    out = {"wrapper_live": live, "note": "wrapper sync DB 不可用时用已导出成员 JSON + 流程具名节点", "roles": {}}
    # first pass without delay copy
    for code, meta in ROLE_META.items():
        if code == "cs_delay_approve":
            continue
        members = []
        seen = set()
        want = set(meta.get("jdy_ids") or [])
        for rel in meta.get("files") or []:
            for m in load_file_members(ROOT / rel, want):
                u = str(m.get("username") or "").strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                members.append({"username": u, "name": m.get("name") or m.get("nickname")})
        for m in meta.get("seed") or []:
            u = str(m.get("username") or "").strip()
            if not u or u in seen:
                continue
            seen.add(u)
            members.append(dict(m))
        if code == "ship_sales_outbound":
            for m in sample_shipment_warehouse_from_raw():
                u = m["username"]
                if u in seen:
                    continue
                seen.add(u)
                members.append(m)
        out["roles"][code] = {"jdy_ids": meta["jdy_ids"], "members": members}

    # 延期审批：与客服内勤同班底（简道云角色成员未单独导出）
    office = out["roles"]["cs_office"]["members"]
    out["roles"]["cs_delay_approve"] = {
        "jdy_ids": ROLE_META["cs_delay_approve"]["jdy_ids"],
        "members": [dict(m) for m in office],
        "note": "对齐客服内勤成员（JDY 同步库不可用）",
    }

    for code, info in out["roles"].items():
        members = info["members"]
        print(f"\n=== {code} n={len(members)} ===")
        for m in members:
            print(f"  {m.get('name')}  {m.get('username')}")

    path = ROOT / "docs" / "product" / "_jdy_nine_flow_role_members.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", path)


if __name__ == "__main__":
    main()
