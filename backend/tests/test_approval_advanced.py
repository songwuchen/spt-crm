"""Advanced approval tests — policy matching, submit, decide, SLA."""

from httpx import AsyncClient


async def test_approval_policy_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, update, delete approval policies."""
    h = auth_headers

    # Create policy
    resp = await client.post("/api/admin/v1/tenant/approval-policies", json={
        "biz_type": "quote_version",
        "name": "High-value quote policy",
        "condition_json": {"amount_gt": 100000},
        "approver_rules_json": [{"type": "role", "value": "admin"}],
        "approval_mode": "sequential",
        "sla_hours": 24,
        "priority": 10,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create policy failed: {data}"
    policy_id = data["data"]["id"]

    # List policies
    lst = await client.get("/api/admin/v1/tenant/approval-policies", headers=h)
    assert lst.json()["code"] == 0
    assert any(p["id"] == policy_id for p in lst.json()["data"])

    # Filter by biz_type
    lst2 = await client.get("/api/admin/v1/tenant/approval-policies?biz_type=quote_version", headers=h)
    assert lst2.json()["code"] == 0
    assert all(p["biz_type"] == "quote_version" for p in lst2.json()["data"])

    # Update policy
    upd = await client.put(f"/api/admin/v1/tenant/approval-policies/{policy_id}", json={
        "sla_hours": 48, "enabled": False,
    }, headers=h)
    assert upd.json()["code"] == 0

    # Delete policy
    dl = await client.delete(f"/api/admin/v1/tenant/approval-policies/{policy_id}", headers=h)
    assert dl.json()["code"] == 0


async def test_submit_approval_with_assignee(client: AsyncClient, auth_headers: dict):
    """Submit an approval flow with explicit assignees, then decide."""
    h = auth_headers

    # Get current user ID from token
    me = await client.get("/api/v1/auth/me", headers=h)
    user_id = me.json()["data"]["id"]
    user_name = me.json()["data"]["real_name"] or me.json()["data"]["username"]

    # Create a customer+project+quote for realistic biz_id
    cust = await client.post("/api/v1/customers", json={
        "name": "Approval Corp", "industry": "Tech", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    # Submit approval
    resp = await client.post("/api/v1/approvals", json={
        "biz_type": "change_request",
        "biz_id": cust_id,  # using cust_id as fake biz_id
        "title": "Test Approval",
        "assignee_ids": [user_id],
        "assignee_names": [user_name],
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Submit approval failed: {data}"
    flow_id = data["data"]["id"]

    # Get flow detail
    detail = await client.get(f"/api/v1/approvals/{flow_id}", headers=h)
    assert detail.json()["code"] == 0
    assert detail.json()["data"]["status"] == "pending"
    tasks = detail.json()["data"].get("tasks", [])
    assert len(tasks) == 1

    # Decide: approve
    task_id = tasks[0]["id"]
    dec = await client.post(f"/api/v1/approvals/tasks/{task_id}/decide", json={
        "action": "approved",
        "comment": "LGTM",
    }, headers=h)
    assert dec.json()["code"] == 0
    assert dec.json()["data"]["status"] == "approved"

    # Cleanup
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_approval_no_auth(client: AsyncClient):
    """Approval endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/approvals")
    assert resp.json()["code"] != 0
