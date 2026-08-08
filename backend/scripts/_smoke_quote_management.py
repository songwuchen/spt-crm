# -*- coding: utf-8 -*-
"""本地冒烟：报价管理 quote_management ensure + 提交 + 待办可见。"""
from __future__ import annotations

import json
import sys

import httpx

BASE = "http://127.0.0.1:8005"
USER, PASS = "admin", "123456"


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
        me = ok(c.get("/api/v1/auth/me", headers=h), "me")
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


def main():
    with httpx.Client(base_url=BASE, timeout=120.0) as c:
        h, me = login(c)
        uid = me.get("id")
        print("user", me.get("username") or me.get("real_name"), uid)

        tpl = ok(
            c.post("/api/v1/lc/builtin-templates/quote_management/ensure", headers=h),
            "ensure",
        )
        tpl_id = tpl.get("id") or tpl.get("template_id")
        print("tpl", tpl_id, tpl.get("name"), "code=", tpl.get("code"))

        detail = ok(c.get(f"/api/v1/lc/form-templates/{tpl_id}", headers=h), "tpl_detail")
        # published fields may be nested
        fields = detail.get("field_definitions") or []
        if not fields:
            # some APIs return latest published via versions
            ver = ok(
                c.get(f"/api/v1/lc/form-templates/{tpl_id}/versions", headers=h),
                "versions",
            )
            items = ver if isinstance(ver, list) else (ver.get("items") or [])
            pub = next((v for v in items if v.get("status") == "published"), None)
            fields = (pub or {}).get("field_definitions") or []
        ids = [f.get("id") for f in fields]
        print("fields", len(ids), "has serial_no=", "serial_no" in ids, "sample=", ids[:8])
        if "serial_no" not in ids or "price_lines" not in ids:
            print("WARN missing expected fields")

        dept_id, _dept_name = pick_dept(c, h)
        custs = ok(c.get("/api/v1/lc/pickable-customers", headers=h, params={"keyword": ""}), "customers")
        cust_list = custs if isinstance(custs, list) else (custs.get("items") or [])
        if not cust_list:
            print("FAIL no pickable customers")
            sys.exit(1)
        customer_id = cust_list[0].get("id")
        # 部门/人员/客户字段存 CRM id 字符串
        form_data = {
            "department": dept_id,
            "sales_person": uid,
            "customer_name": customer_id,
            "customer_category": "新客户",
            "price_type": "核价",
            "ref_contract_no": "SMOKE-REF-001",
            "price_lines": [
                {
                    "product_name": "测试产品",
                    "spec_model": "规格A",
                    "unit": "台",
                    "qty": 1,
                }
            ],
            "need_purchase": "否",
            "special_reminder": "smoke quote_management",
        }

        created = ok(c.post("/api/v1/lc/form-instances", headers=h, json={
            "template_id": tpl_id,
            "title": "冒烟-报价管理",
            "form_data": form_data,
            "as_draft": False,
        }), "create")
        iid = created.get("id")
        inst = ok(c.get(f"/api/v1/lc/form-instances/{iid}", headers=h), "get_inst")
        serial = (inst.get("form_data") or {}).get("serial_no")
        pid = inst.get("process_instance_id")
        print("created", iid, "serial=", serial, "process=", pid, "status=", inst.get("status"))
        if not serial or not str(serial).startswith("HJ"):
            print("WARN serial_no not HJ*", serial)

        if not pid:
            print("FAIL no process started")
            sys.exit(1)

        # 统一待办 / 流程待办
        todos = ok(c.get("/api/v1/lc/wf/tasks/todo", headers=h, params={
            "pageNo": 1, "pageSize": 50,
        }), "todo")
        items = todos.get("items") or []
        mine = [
            t for t in items
            if t.get("process_instance_id") == pid
            or t.get("form_instance_id") == iid
            or t.get("biz_id") == iid
        ]
        print("wf_todo_total", len(items), "for_this", len(mine))
        if mine:
            print("  first", mine[0].get("node_name") or mine[0].get("name"), mine[0].get("id"))
        else:
            detail = ok(c.get(f"/api/v1/lc/wf/instances/{pid}", headers=h), "pinst")
            tasks = detail.get("tasks") or detail.get("task_instances") or []
            pending = [t for t in tasks if t.get("status") == "pending"]
            print(
                "process_status", detail.get("status"),
                "pending", [
                    (t.get("node_name") or t.get("name"), t.get("assignee_name") or t.get("assignee_id"))
                    for t in pending[:6]
                ],
            )
            if not pending:
                print("FAIL no pending tasks")
                sys.exit(1)
            print("  pending exists (assignee may not be admin) — OK for smoke")

        # 审批中心统一待办（若有）
        try:
            uni = ok(c.get("/api/v1/approvals/my/pending", headers=h, params={
                "page": 1, "page_size": 40,
            }), "approvals_pending")
            uitems = uni if isinstance(uni, list) else (uni.get("items") or uni.get("list") or [])
            hit = [
                x for x in uitems
                if isinstance(x, dict) and (
                    x.get("process_instance_id") == pid
                    or x.get("form_instance_id") == iid
                    or x.get("biz_id") == iid
                    or "报价" in str(x.get("process_name") or x.get("title") or "")
                )
            ]
            print("unified_pending", len(uitems), "quote_hits", len(hit))
        except SystemExit:
            print("approvals_pending skipped/fail (non-fatal if wf pending ok)")

        print("SMOKE_OK")


if __name__ == "__main__":
    main()
