"""已办节点补改 field_perms 合并、写回与数据日志摘要。"""
from app.domains.lowcode.wf_field_writeback import (
    _merge_field_perm_lists,
    merge_retroactive_form_writes,
    retroactive_change_summary,
    user_can_retroactive_edit,
)


def test_merge_field_perm_lists_required_wins():
    merged = _merge_field_perm_lists([
        [{"field": "fill_code", "access": "editable", "node_name": "物料编码"}],
        [{"field": "fill_code", "access": "required", "node_name": "物料编码"}],
        [{"field": "inspectors", "access": "editable", "node_name": "检验"}],
    ])
    by_field = {p["field"]: p for p in merged}
    assert by_field["fill_code"]["access"] == "required"
    assert by_field["inspectors"]["access"] == "editable"


def test_merge_retroactive_form_writes_overlays_allowed():
    sanitized = {"submitter": "u1", "fill_code": "old"}
    raw = {"submitter": "u2", "fill_code": "new-code"}
    retro = [{"field": "fill_code", "access": "editable", "node_name": "物料编码"}]
    out = merge_retroactive_form_writes(sanitized, raw, retro)
    assert out["submitter"] == "u1"
    assert out["fill_code"] == "new-code"


def test_user_can_retroactive_edit_requires_permission():
    assert not user_can_retroactive_edit(None, "running")
    assert not user_can_retroactive_edit({"permissions": ["form_data:view"]}, "running")
    assert user_can_retroactive_edit({"permissions": ["form_data:edit"]}, "running")
    assert user_can_retroactive_edit({"permissions": ["form_data:edit"]}, "completed")
    assert not user_can_retroactive_edit({"permissions": ["form_data:edit"]}, "archived")


def test_retroactive_change_summary_includes_node():
    changes = {"fill_code": {"old": "a", "new": "b"}}
    perms = [{"field": "fill_code", "access": "editable", "node_name": "物料编码"}]
    field_defs = [{"id": "fill_code", "label": "物料编码", "type": "text"}]
    summary = retroactive_change_summary(changes, perms, field_defs)
    assert "补改已办节点字段" in summary
    assert "物料编码" in summary
