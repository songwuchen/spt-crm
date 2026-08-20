"""把生成物里客服安排1 的 sales_manager 改成 cs_arrange。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

GEN = Path(__file__).resolve().parents[1] / "app" / "domains" / "lowcode" / "_customer_service_jdy_generated.py"

WANT = {
    "type": "specified_role",
    "value": "cs_arrange",
    "exclude_initiator": True,
    "jdy_role_hint": "服务申请及反馈-客服安排",
}


def main() -> None:
    text = GEN.read_text(encoding="utf-8")
    marker = "r'''"
    i = text.index(marker) + len(marker)
    j = text.rindex("'''")
    d = json.loads(text[i:j])
    form = d["cs_service_request"]
    nodes = form.get("flow_nodes") or (form.get("workflow") or {}).get("nodes") or []
    changed = 0
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("id") == "n6__1" or n.get("name") == "客服安排1":
            ar = n.get("approver_rule") or {}
            if ar.get("value") != "cs_arrange":
                n["approver_rule"] = dict(WANT)
                changed += 1
                print("patched", n.get("id"), n.get("name"), "from", ar)
    notes = form.get("notes")
    if isinstance(notes, list):
        for i, note in enumerate(notes):
            if isinstance(note, str) and "客服安排1" in note and "sales_manager" in note:
                notes[i] = "审批「客服安排1」JDY 角色「服务申请及反馈-客服安排」→ CRM 角色 cs_arrange"
                changed += 1
    if not changed:
        print("already ok")
        return
    # 保持原文件写法：首行 CUSTOMER_SERVICE_JDY = json.loads(r'''...''')
    prefix = text[: text.index(marker) + len(marker)]
    suffix = text[j:]
    new_json = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    GEN.write_text(prefix + new_json + suffix, encoding="utf-8")
    print("done, changed", changed)


if __name__ == "__main__":
    main()
