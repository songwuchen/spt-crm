"""业务打分字段：创建隐藏 + 节点权限。"""
from app.domains.lowcode.biz_score import (
    apply_biz_score_field_defs,
    apply_biz_score_flow_nodes,
    flow_missing_biz_score_perms,
    strip_biz_score_flow_nodes,
)


def test_apply_biz_score_field_defs():
    fields = [
        {"id": "score_attitude", "type": "number", "label": "态度分数", "required": True},
        {"id": "score_progress", "type": "number", "label": "进度、准确性分数", "required": True},
        {"id": "score_skill", "type": "number", "label": "专业技能分数", "required": True},
        {"id": "score_total", "type": "number", "label": "总分"},
        {"id": "score_date", "type": "datetime", "label": "打分日期"},
        {"id": "remark", "type": "textarea", "label": "备注", "required": True},
        {"id": "department", "type": "department", "label": "部门", "available_on_create": True},
    ]
    apply_biz_score_field_defs(fields)
    for fid in ("score_attitude", "score_progress", "score_skill"):
        fd = next(f for f in fields if f["id"] == fid)
        assert fd["available_on_create"] is False
        assert fd["fill_stage"] == "approver"
        assert fd["required"] is False
        assert "max" in (fd.get("props") or {})
    total = next(f for f in fields if f["id"] == "score_total")
    assert total["type"] == "formula"
    assert "SUM" in (total.get("props") or {}).get("formula", "")
    remark = next(f for f in fields if f["id"] == "remark")
    assert remark["available_on_create"] is False
    assert remark["required"] is False
    assert fields[-1]["available_on_create"] is True  # untouched


def test_strip_biz_score_flow_nodes_with_remark():
    nodes = [{
        "type": "approval",
        "name": "业务反馈",
        "field_perms": [
            {"field": "score_attitude", "access": "required"},
            {"field": "remark", "access": "required"},
            {"field": "biz_feedback", "access": "required"},
        ],
    }]
    changed = strip_biz_score_flow_nodes(nodes, extra_fields=frozenset({"remark"}))
    assert changed is True
    fps = {p["field"] for p in nodes[0]["field_perms"]}
    assert fps == {"biz_feedback"}


def test_apply_biz_score_flow_nodes_and_missing():
    nodes = [
        {"id": "req_n17", "type": "approval", "name": "业务打分"},
        {
            "id": "ins_n21", "type": "approval", "name": "业务反馈",
            "field_perms": [{"field": "biz_feedback", "access": "required"}],
        },
    ]
    assert flow_missing_biz_score_perms(nodes) is True
    apply_biz_score_flow_nodes(nodes)
    assert flow_missing_biz_score_perms(nodes) is False
    score_node = nodes[0]
    fps = {p["field"]: p["access"] for p in score_node["field_perms"]}
    assert fps["score_attitude"] == "required"
    assert fps["score_progress"] == "required"
    assert fps["score_skill"] == "required"
    fb = nodes[1]
    fps2 = {p["field"]: p["access"] for p in fb["field_perms"]}
    assert fps2["biz_feedback"] == "required"
    assert fps2["score_attitude"] == "required"
