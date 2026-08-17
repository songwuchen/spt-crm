"""表单导出：人员/部门 id 转显示名。"""
from __future__ import annotations

from app.domains.lowcode.router import _collect_ref_ids, _fmt_export_cell


def test_collect_ref_ids():
    assert _collect_ref_ids("abc") == ["abc"]
    assert _collect_ref_ids({"id": "u1", "name": "张三"}) == ["u1"]
    assert _collect_ref_ids([{"id": "a"}, "b"]) == ["a", "b"]
    assert _collect_ref_ids(None) == []


def test_fmt_export_department_uses_label_map():
    labels = {"depts": {"d1": "精品砂石事业部"}}
    assert _fmt_export_cell("department", "d1", labels) == "精品砂石事业部"
    assert _fmt_export_cell("department", "d1", None) == "d1"
    assert _fmt_export_cell("dept_code", "03", labels) == "03"


def test_fmt_export_person_multi():
    labels = {"users": {"u1": "张三", "u2": "李四"}}
    assert _fmt_export_cell("person_multi", ["u1", "u2"], labels) == "张三、李四"
