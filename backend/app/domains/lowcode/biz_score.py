# -*- coding: utf-8 -*-
"""方案/安装图「业务打分」字段：创建页隐藏，审批节点填写。

简道云：态度 0–20、进度准确性 0–40、专业技能 0–40；总分 = 三者之和。
"""
from __future__ import annotations

from typing import Any

SCORE_REQUIRED_FIELDS = ("score_attitude", "score_progress", "score_skill")
SCORE_OPTIONAL_FIELDS = ("score_date",)
SCORE_TOTAL_FIELD = "score_total"

_SCORE_LIMITS: dict[str, dict[str, Any]] = {
    "score_attitude": {"min": 0, "max": 20, "precision": 1},
    "score_progress": {"min": 0, "max": 40, "precision": 1},
    "score_skill": {"min": 0, "max": 40, "precision": 1},
}

BIZ_SCORE_NODE_NAMES = frozenset({"业务打分", "业务反馈"})

BIZ_SCORE_FIELD_PERMS: list[dict[str, str]] = [
    {"field": "score_attitude", "access": "required"},
    {"field": "score_progress", "access": "required"},
    {"field": "score_skill", "access": "required"},
    {"field": "score_date", "access": "editable"},
]


def apply_biz_score_field_defs(field_defs: list[dict[str, Any]]) -> None:
    """创建隐藏打分项；总分改为公式求和。"""
    for fd in field_defs or []:
        if not isinstance(fd, dict):
            continue
        fid = fd.get("id")
        if fid in _SCORE_LIMITS:
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False  # 必填下沉到节点 field_perms
            props = dict(fd.get("props") or {}) if isinstance(fd.get("props"), dict) else {}
            props.update(_SCORE_LIMITS[fid])
            fd["props"] = props
        elif fid == SCORE_TOTAL_FIELD:
            fd["type"] = "formula"
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
            fd["props"] = {
                "formula": "SUM($score_attitude#,$score_progress#,$score_skill#)",
            }
        elif fid == "score_date":
            fd["available_on_create"] = False
            fd["fill_stage"] = "approver"
            fd["required"] = False
            props = dict(fd.get("props") or {}) if isinstance(fd.get("props"), dict) else {}
            props["default_today"] = True
            fd["props"] = props


def _merge_score_perms(existing: list | None) -> list[dict[str, str]]:
    by_field: dict[str, str] = {}
    for p in existing or []:
        if not isinstance(p, dict) or not p.get("field"):
            continue
        acc = p.get("access") or "editable"
        if acc not in ("editable", "required"):
            acc = "editable"
        by_field[str(p["field"])] = acc
    for p in BIZ_SCORE_FIELD_PERMS:
        fid = p["field"]
        # 已有 required 保留；否则用打分规则
        if fid not in by_field or by_field[fid] != "required":
            by_field[fid] = p["access"]
    return [{"field": k, "access": v} for k, v in by_field.items()]


def apply_biz_score_flow_nodes(nodes: list[dict[str, Any]] | None) -> None:
    """给「业务打分」「业务反馈」节点挂上三项分数（+打分日期）可填权限。"""
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") not in BIZ_SCORE_NODE_NAMES:
            continue
        n["field_perms"] = _merge_score_perms(n.get("field_perms"))


SCORE_DROP_FIELDS = frozenset(
    SCORE_REQUIRED_FIELDS + SCORE_OPTIONAL_FIELDS + (SCORE_TOTAL_FIELD,),
)


def strip_biz_score_flow_nodes(nodes: list[dict[str, Any]] | None) -> bool:
    """从节点 field_perms 去掉业务打分字段。返回是否有改动。"""
    changed = False
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        perms = n.get("field_perms") or []
        if not perms:
            continue
        kept = [
            p for p in perms
            if isinstance(p, dict) and p.get("field") not in SCORE_DROP_FIELDS
        ]
        if len(kept) != len(perms):
            n["field_perms"] = kept
            changed = True
    return changed


def flow_has_biz_score_perms(nodes: list | None) -> bool:
    """节点 field_perms 仍含业务打分字段（方案管理需剥离时用）。"""
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        for p in n.get("field_perms") or []:
            if isinstance(p, dict) and p.get("field") in SCORE_DROP_FIELDS:
                return True
    return False


def flow_missing_biz_score_perms(nodes: list | None) -> bool:
    """「业务打分」或「业务反馈」节点缺少三项分数权限 → 需要升级。"""
    saw_target = False
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") not in BIZ_SCORE_NODE_NAMES:
            continue
        saw_target = True
        fps = {
            p.get("field")
            for p in (n.get("field_perms") or [])
            if isinstance(p, dict)
        }
        if not set(SCORE_REQUIRED_FIELDS) <= fps:
            return True
    # 方案流应有「业务打分」；若节点都没有则不算 missing（避免误伤无关流）
    return False if saw_target else False


def flow_missing_chief_gm_perm(nodes: list | None) -> bool:
    """方案管理「总工审批」缺少 need_gm_approval 必填权限 → 需升级。"""
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") != "总工审批":
            continue
        fps = {
            p.get("field")
            for p in (n.get("field_perms") or [])
            if isinstance(p, dict) and p.get("access") == "required"
        }
        if "need_gm_approval" not in fps:
            return True
    return False


def apply_chief_gm_flow_nodes(nodes: list[dict[str, Any]] | None) -> None:
    """给所有「总工审批」节点挂上 need_gm_approval=required。"""
    for n in nodes or []:
        if not isinstance(n, dict) or n.get("type") != "approval":
            continue
        if n.get("name") != "总工审批":
            continue
        perms = [
            p for p in (n.get("field_perms") or [])
            if isinstance(p, dict) and p.get("field")
        ]
        by_f = {str(p["field"]): str(p.get("access") or "editable") for p in perms}
        by_f["need_gm_approval"] = "required"
        n["field_perms"] = [{"field": k, "access": v} for k, v in by_f.items()]


def flow_missing_install_gm_branch(nodes: list | None, routes: list | None) -> bool:
    """无合同号总工未按 need_gm_approval 分支到总经理审批。"""
    has_node = any(
        isinstance(n, dict) and n.get("id") == "ins_n_gm"
        for n in (nodes or [])
    )
    has_route = any(
        isinstance(r, dict)
        and r.get("source") == "ins_n7"
        and r.get("target") == "ins_n_gm"
        and "need_gm_approval" in str(r.get("condition") or "")
        for r in (routes or [])
    )
    return not (has_node and has_route)


def apply_install_gm_branch(nodes: list[dict[str, Any]], routes: list[dict[str, Any]]) -> None:
    """就地补无合同号 need_gm → 总经理审批 分支（保留已 remap 的审批人）。"""
    import copy

    req_gm = next((n for n in nodes if isinstance(n, dict) and n.get("id") == "req_n18"), None)
    if not any(isinstance(n, dict) and n.get("id") == "ins_n_gm" for n in nodes):
        gm_rule = copy.deepcopy((req_gm or {}).get("approver_rule")) or {
            "type": "specified_user",
            "value": "02336214315748",
        }
        # 若现网抄送总经理已 remap，优先复用其审批人作为总经理审批人
        cc = next((n for n in nodes if isinstance(n, dict) and n.get("id") == "ins_n12"), None)
        if isinstance(cc, dict) and isinstance(cc.get("approver_rule"), dict):
            gm_rule = copy.deepcopy(cc["approver_rule"])
        nodes.append({
            "id": "ins_n_gm",
            "type": "approval",
            "name": "总经理审批",
            "approver_rule": gm_rule,
            "multi_mode": (req_gm or {}).get("multi_mode") or "or_sign",
            "empty_strategy": (req_gm or {}).get("empty_strategy") or "auto_approve",
            "field_perms": [],
        })

    kept = [r for r in routes if not (isinstance(r, dict) and r.get("source") == "ins_n7")]
    # 保留原 is_xiaomeng→周经理 边的其它元数据（若有）
    kept.extend([
        {
            "id": "ins_r_n7_gm",
            "source": "ins_n7",
            "target": "ins_n_gm",
            "exclusive_group": "ex_n7",
            "condition": {"field": "need_gm_approval", "operator": "eq", "value": "是"},
        },
        {
            "id": "ins_r_n7_zhou",
            "source": "ins_n7",
            "target": "ins_n9",
            "exclusive_group": "ex_n7",
            "condition": {"field": "is_xiaomeng", "operator": "eq", "value": "是"},
        },
        {
            "id": "ins_r_n7_design",
            "source": "ins_n7",
            "target": "ins_n5",
            "exclusive_group": "ex_n7",
        },
        {
            "id": "ins_r_n7_cc_gm",
            "source": "ins_n7",
            "target": "ins_n12",
            "always": True,
            "condition": {"field": "need_gm_approval", "operator": "eq", "value": "否"},
        },
    ])
    if not any(
        isinstance(r, dict) and r.get("source") == "ins_n_gm" and r.get("target") == "ins_n5"
        for r in kept
    ):
        kept.append({
            "id": "ins_r_gm_design",
            "source": "ins_n_gm",
            "target": "ins_n5",
            "condition": None,
        })
    routes[:] = kept
