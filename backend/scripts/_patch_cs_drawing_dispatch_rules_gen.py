# -*- coding: utf-8 -*-
"""Patch cs_drawing_request.rule_definitions into _customer_service_jdy_generated.py."""
from __future__ import annotations

import json
from pathlib import Path

from app.domains.lowcode.cs_drawing_request_fields import CS_DRAWING_DISPATCH_RULES

GEN = Path(__file__).resolve().parents[1] / "app" / "domains" / "lowcode" / "_customer_service_jdy_generated.py"


def main() -> None:
    text = GEN.read_text(encoding="utf-8")
    marker = "json.loads(r'''"
    i = text.find(marker)
    if i < 0:
        raise SystemExit("marker not found")
    start = i + len(marker)
    end = text.rfind("''')")
    data = json.loads(text[start:end])
    form = data.get("cs_drawing_request")
    if not isinstance(form, dict):
        raise SystemExit("cs_drawing_request missing")
    form["rule_definitions"] = [dict(r) for r in CS_DRAWING_DISPATCH_RULES]
    notes = list(form.get("notes") or [])
    note = f"fieldShowRules → {len(CS_DRAWING_DISPATCH_RULES)} 条显隐/条件必填规则"
    notes = [n for n in notes if "fieldShowRules" not in str(n)]
    notes.append(note)
    form["notes"] = notes
    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    GEN.write_text(text[:start] + new_json + text[end:], encoding="utf-8")
    print("patched rules", len(form["rule_definitions"]))


if __name__ == "__main__":
    main()
