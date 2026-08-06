# -*- coding: utf-8 -*-
"""给同源多出边补 exclusive_group（画布 if/else 互斥 + 引擎选路）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "app/domains/lowcode/_drawing_jdy_generated.py",
    ROOT / "app/domains/lowcode/_scheme_management_generated.py",
    ROOT / "app/domains/lowcode/_prod_card_jdy_generated.py",
]


def patch_routes(routes: list) -> int:
    by_src: dict[str, list] = {}
    for r in routes or []:
        if not isinstance(r, dict) or r.get("always"):
            continue
        by_src.setdefault(str(r.get("source") or ""), []).append(r)
    n = 0
    for src, outs in by_src.items():
        if len(outs) < 2:
            continue
        gid = f"ex_{src}"
        for r in outs:
            if r.get("exclusive_group") != gid:
                r["exclusive_group"] = gid
                n += 1
    return n


def patch_file(path: Path) -> int:
    t = path.read_text(encoding="utf-8")
    m = re.search(r"json\.loads\(r'''(.+)'''\)", t, re.S)
    if not m:
        print("no json", path.name)
        return 0
    data = json.loads(m.group(1))
    changed = 0

    def walk(obj):
        nonlocal changed
        if isinstance(obj, dict):
            if isinstance(obj.get("flow_routes"), list):
                changed += patch_routes(obj["flow_routes"])
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    path.write_text(
        t[: m.start(1)] + json.dumps(data, ensure_ascii=False) + t[m.end(1) :],
        encoding="utf-8",
    )
    print(path.name, "patched edges", changed)
    return changed


def main():
    total = 0
    for f in FILES:
        if f.exists():
            total += patch_file(f)
    print("DONE", total)


if __name__ == "__main__":
    main()
