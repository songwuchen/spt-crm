#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
raw = json.loads((ROOT / "docs/product/_jdy_cs_product_return_workflows_raw.json").read_text(encoding="utf-8"))
flows = raw["workflow_config"]["flows"]
by_id = {f["flowId"]: f for f in flows if isinstance(f, dict) and "flowId" in f}

for fid in sorted(by_id.keys()):
    if fid in (-1, 0):
        continue
    f = by_id[fid]
    c = f.get("chargers") or {}
    print(f"=== {fid} {f.get('name')} ({f.get('type')}) ===")
    roles = [r.get("name") for r in (c.get("roles") or []) if isinstance(r, dict)]
    users = [
        f"{u.get('username')}/{u.get('name') or ''}"
        for u in (c.get("users") or [])
        if isinstance(u, dict) and u.get("username")
    ]
    widgets = c.get("widgets") or []
    dm = c.get("deptManager") or {}
    print("  roles:", roles)
    print("  users:", users)
    print("  widgets:", widgets)
    print("  deptManager:", {k: dm.get(k) for k in ("creator", "charger", "userWidgets", "deptWidgets") if dm.get(k)})
    outs = []
    for tid, f2 in by_id.items():
        cond = (f2.get("condition") or {}).get(str(fid))
        if cond is not None:
            tag = "isElse" if cond.get("isElse") else ("__always" if not cond.get("cond") else cond.get("cond"))
            outs.append((tid, f2.get("name"), tag))
    print("  ->", outs)
    print()
