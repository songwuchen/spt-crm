# -*- coding: utf-8 -*-
"""本地冒烟：方案管理 scheme_management 创建 + 审批推进。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import httpx

BASE = "http://127.0.0.1:8004"
USER, PASS = "admin", "admin123"


def ok(r: httpx.Response, label: str):
    try:
        body = r.json()
    except Exception:
        print(label, "HTTP", r.status_code, r.text[:500])
        sys.exit(1)
    if body.get("code") != 0:
        print(label, "FAIL", json.dumps(body, ensure_ascii=False)[:1200])
        sys.exit(1)
    return body.get("data")


def login(c: httpx.Client) -> tuple[dict, dict]:
    data = ok(c.post("/api/v1/auth/login", json={"username": USER, "password": PASS}), "login")
    h = {"Authorization": f"Bearer {data['access_token']}"}
    me = data.get("user") or {}
    if not me.get("id"):
        # 部分登录响应把用户放在 data 顶层
        me = {
            "id": data.get("user_id") or data.get("id") or data.get("sub"),
            "real_name": data.get("real_name") or data.get("username") or USER,
            "username": data.get("username") or USER,
        }
    return h, me


def pick_dept(c: httpx.Client, h: dict) -> tuple[str, str]:
    tree = ok(c.get("/api/v1/lc/pickable-departments", headers=h), "depts")
    nodes = tree if isinstance(tree, list) else (tree.get("items") or tree.get("data") or [])
    def first(ns):
        for n in ns or []:
            nid = n.get("id") or n.get("value")
            if nid:
                return nid, n.get("name") or n.get("title") or n.get("label") or nid
            hit = first(n.get("children") or [])
            if hit:
                return hit
        return None
    hit = first(nodes)
    if not hit:
        print("no department found", tree)
        sys.exit(1)
    return hit


def ensure_tpl(c: httpx.Client, h: dict) -> dict:
    return ok(c.post("/api/v1/lc/builtin-templates/scheme_management/ensure", headers=h), "ensure")


def create_inst(c: httpx.Client, h: dict, tpl_id: str, form_data: dict, title: str) -> dict:
    return ok(c.post("/api/v1/lc/form-instances", headers=h, json={
        "template_id": tpl_id,
        "title": title,
        "form_data": form_data,
        "as_draft": False,
    }), f"create:{title}")


def drive_approvals(c: httpx.Client, h: dict, form_inst_id: str, max_steps: int = 40) -> str:
    """推进与该表单实例相关的待办，直到无待办或完成。"""
    last_status = "?"
    for step in range(max_steps):
        inst = ok(c.get(f"/api/v1/lc/form-instances/{form_inst_id}", headers=h), f"get#{step}")
        last_status = inst.get("status") or last_status
        pid = inst.get("process_instance_id")
        print(f"  step{step}: form_status={last_status} process={pid}")
        if last_status in ("completed", "approved", "rejected", "cancelled"):
            return last_status
        if not pid:
            print("  no process_instance_id — 可能未绑流程或起流失败")
            return last_status

        todos = ok(c.get("/api/v1/lc/wf/tasks/todo", headers=h, params={
            "pageNo": 1, "pageSize": 50,
        }), f"todo#{step}")
        items = todos.get("items") or []
        mine = [t for t in items if (
            t.get("process_instance_id") == pid
            or t.get("form_instance_id") == form_inst_id
            or t.get("biz_id") == form_inst_id
        )]
        if not mine:
            detail = ok(c.get(f"/api/v1/lc/wf/instances/{pid}", headers=h), f"pinst#{step}")
            last_status = detail.get("status") or last_status
            print(f"  process_status={last_status} todos_for_me=0 total_todo={len(items)}")
            if last_status in ("completed", "approved", "rejected", "cancelled"):
                return last_status
            tasks = detail.get("tasks") or detail.get("task_instances") or []
            pending = [t for t in tasks if t.get("status") == "pending"]
            print(f"  pending_tasks={[(t.get('node_name') or t.get('name'), t.get('assignee_name') or t.get('assignee_id')) for t in pending[:8]]}")
            if not pending:
                return last_status
            print("  stuck: pending exists but not in my todo")
            return last_status

        t = mine[0]
        tid = t.get("task_id") or t.get("id")
        node = t.get("node_name") or t.get("name")
        print(f"  approve todo: {node} tid={tid}")
        ok(c.post(f"/api/v1/lc/wf/tasks/{tid}/act", headers=h, json={
            "action": "approve", "comment": f"smoke {node}",
        }), f"act#{step}")
    return last_status


def main():
    c = httpx.Client(base_url=BASE, timeout=120.0, trust_env=False)
    h, me = login(c)
    uid = me.get("id") or me.get("sub")
    if not uid:
        # /me
        me2 = ok(c.get("/api/v1/auth/me", headers=h), "me")
        uid = me2.get("id")
        me = me2
    uname = me.get("real_name") or me.get("username") or USER
    did, dname = pick_dept(c, h)
    print(f"user={str(uid)[:8]}…({uname}) dept={did[:8]}…({dname})")

    tpl = ensure_tpl(c, h)
    tpl_id = tpl["id"]
    print(f"tpl={tpl_id[:8]} name={tpl.get('name')} code={tpl.get('code')}")

    form_design = ok(c.get(f"/api/v1/lc/form-templates/{tpl_id}/design", headers=h), "tpl_design")
    fields = form_design.get("field_definitions") or []
    print(f"published fields={len(fields)}")
    assert any(f.get("id") == "scheme_type" for f in fields), "missing scheme_type"
    assert len(fields) >= 50, f"too few fields: {len(fields)}"

    defs = ok(c.get("/api/v1/lc/wf/definitions", headers=h, params={"pageNo": 1, "pageSize": 100}), "defs")
    sm_def = next((i for i in (defs.get("items") or []) if i.get("code") == "SYS_SCHEME_MANAGEMENT"
                   or i.get("form_template_id") == tpl_id or i.get("name") == "方案管理"), None)
    print("flow_def:", sm_def.get("code") if sm_def else None, sm_def.get("name") if sm_def else "MISSING")

    if sm_def:
        wf_design = ok(c.get(f"/api/v1/lc/wf/definitions/{sm_def['id']}/design", headers=h), "wf_design")
        nodes = wf_design.get("node_definitions") or []
        changed = False
        for n in nodes:
            if n.get("type") != "approval":
                continue
            # 全部审批节点指定当前登录用户，便于单人冒烟
            n["approver_rule"] = {
                "type": "specified_user", "value": uid, "exclude_initiator": False,
            }
            changed = True
        if changed:
            ok(c.post(f"/api/v1/lc/wf/definitions/{sm_def['id']}/design", headers=h, json={
                "node_definitions": nodes,
                "route_definitions": wf_design.get("route_definitions") or [],
                "approver_rules": wf_design.get("approver_rules") or [],
            }), "save_design")
            ok(c.post(f"/api/v1/lc/wf/definitions/{sm_def['id']}/publish", headers=h), "publish")
            print("published: all approvals -> current user")

    stamp = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
    now = datetime.now(timezone.utc).isoformat()

    req_data = {
        "scheme_type": "requisition",
        "apply_datetime": now,
        "department": did,
        "applicant": uid,
        "order_person": uid,
        "apply_reason": f"冒烟领用 {stamp}",
        "transfer_channel": "钉钉",
        "drawing_type": "生产图",
        "attachment_name": "冒烟附件",
        "design_dispatch": "总部单",
        "design_assignees": uid,
        "offices": did,
        "order_date": now,
        "need_gm_approval": "否",
        "involve_std_drawing": "否",
        "contract_no": f"CT-SMOKE-{stamp}",
    }
    print("\n=== CREATE requisition ===")
    r1 = create_inst(c, h, tpl_id, req_data, f"方案管理-领用-{stamp}")
    print("created", r1)
    print("=== APPROVE requisition ===")
    st1 = drive_approvals(c, h, r1["id"])
    print("FINAL requisition:", st1)

    ins_data = {
        "scheme_type": "install",
        "apply_datetime": now,
        "department": did,
        "applicant": uid,
        "order_person": uid,
        "is_new_project": "否",
        "project_no": f"PJ-{stamp}",
        "is_xiaomeng": "是",
        "drawing_issue_type": "领图",
        "drawing_types": ["安装图"],
        "pickup_purpose": "报价",
        "apply_reason_star": f"冒烟安装图 {stamp}",
        "biz_feedback": "结果未出",
        "design_dispatch": "总部单",
        "design_assignees": uid,
        "need_submit_drawing": "图纸已交",
        "offices_multi": [did],
        "order_date": now,
        "attachment_names": "冒烟",
        "score_attitude": 5,
        "score_progress": 5,
        "score_skill": 5,
        "remark": "smoke",
    }
    print("\n=== CREATE install ===")
    r2 = create_inst(c, h, tpl_id, ins_data, f"方案管理-安装图-{stamp}")
    print("created", r2)
    print("=== APPROVE install ===")
    st2 = drive_approvals(c, h, r2["id"])
    print("FINAL install:", st2)

    print("\n======== SUMMARY ========")
    print(f"requisition: id={r1['id']} create_status={r1.get('status')} final={st1}")
    print(f"install:     id={r2['id']} create_status={r2.get('status')} final={st2}")
    ok_create = r1.get("status") == "running" and r2.get("status") == "running"
    ok_done = st1 == "completed" and st2 == "completed"
    print("create_and_start_ok:", ok_create)
    print("approve_completed_ok:", ok_done)
    if not ok_create:
        sys.exit(1)
    if not ok_done:
        sys.exit(2)


if __name__ == "__main__":
    main()
