"""客服领图：设计单分派联动显隐（对齐简道云 field_show_rules）。"""

from app.domains.lowcode.builtin_templates import get_builtin
from app.domains.lowcode.cs_drawing_request_fields import (
    CS_DRAWING_DISPATCH_RULES,
    apply_cs_drawing_request_rules,
)
from app.domains.lowcode.rule_engine import compute_field_states


def test_cs_drawing_dispatch_rules_present():
    bt = get_builtin("cs_drawing_request")
    rules = bt.get("rule_definitions") or []
    ids = {r.get("id") for r in rules if isinstance(r, dict)}
    for r in CS_DRAWING_DISPATCH_RULES:
        assert r["id"] in ids


def test_cs_drawing_dispatch_visibility_matrix():
    bt = get_builtin("cs_drawing_request")
    fields = bt["field_definitions"]
    rules = apply_cs_drawing_request_rules(bt.get("rule_definitions") or [])
    perms = [
        {"fieldId": x, "access": "required"}
        for x in (
            "design_dispatch",
            "transfer_packaging_users",
            "design_assignees",
            "offices",
            "order_date",
        )
    ]
    expect = {
        "包装单": (True, False),
        "总部单": (False, True),
        "共同": (True, True),
        "新乡单": (True, False),
        "郑州单": (True, False),
    }
    for disp, (t_vis, a_vis) in expect.items():
        st = compute_field_states(fields, {"design_dispatch": disp}, rules, perms)
        assert st["transfer_packaging_users"]["visible"] is t_vis
        assert st["design_assignees"]["visible"] is a_vis
        assert st["offices"]["visible"] is True
        assert st["transfer_packaging_users"]["required"] is t_vis
        assert st["design_assignees"]["required"] is a_vis
