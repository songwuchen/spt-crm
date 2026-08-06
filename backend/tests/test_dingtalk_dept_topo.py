# -*- coding: utf-8 -*-
"""部门同步：拓扑排序与 parent 回写。"""
from app.common.dingtalk_sync import _topo_sort_dingtalk_depts, _dept_path, _rebuild_department_paths


def test_topo_sort_child_before_parent_by_numeric_parentid():
    """旧 bug：子部门 parentid 数值更小会排到父部门前面。"""
    # Grand(parentid=1) id=5000; Mid(parentid=5000) id=100; Deep(parentid=100) id=200
    # 按 parentid 数值排序会变成 Deep → Mid → Grand（Deep 的 parentid=100 < Mid 的 5000）
    depts = [
        {"id": 200, "name": "设计一室", "parentid": 100, "order": 1},
        {"id": 100, "name": "新乡研发中心", "parentid": 5000, "order": 1},
        {"id": 5000, "name": "技术总工", "parentid": 1, "order": 1},
        {"id": 6000, "name": "中央研究院", "parentid": 5000, "order": 2},
    ]
    ordered = _topo_sort_dingtalk_depts(depts)
    names = [d["name"] for d in ordered]
    assert names.index("技术总工") < names.index("新乡研发中心")
    assert names.index("技术总工") < names.index("中央研究院")
    assert names.index("新乡研发中心") < names.index("设计一室")


def test_dept_path_and_rebuild():
    class D:
        def __init__(self, id, name, parent_id=None, path=""):
            self.id = id
            self.name = name
            self.parent_id = parent_id
            self.path = path

    root = D("1", "威猛股份", None, "/wrong/")
    tech = D("2", "技术总工", "1", "/wrong/技术总工/")
    child = D("3", "新乡研发中心", None, "/新乡研发中心/")  # 误挂顶层
    child.parent_id = "2"  # 纠偏后
    existing = [root, tech, child]
    n = _rebuild_department_paths(existing)
    assert n >= 1
    assert root.path == "/威猛股份/"
    assert tech.path == "/威猛股份/技术总工/"
    assert child.path == "/威猛股份/技术总工/新乡研发中心/"
    assert _dept_path("x", tech) == "/威猛股份/技术总工/x/"
