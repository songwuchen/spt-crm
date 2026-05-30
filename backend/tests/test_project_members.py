"""Project member (多部门/多人协作) + sub-module assignee tests."""

from httpx import AsyncClient


async def _setup_project(client: AsyncClient, h: dict) -> tuple[str, str]:
    cust = await client.post("/api/v1/customers", json={"name": "Member Test Corp"}, headers=h)
    cust_id = cust.json()["data"]["id"]
    proj = await client.post("/api/v1/projects", json={
        "name": "Member Test Project", "customer_id": cust_id, "amount_expect": 100000,
    }, headers=h)
    return cust_id, proj.json()["data"]["id"]


async def _cleanup(client: AsyncClient, h: dict, proj_id: str, cust_id: str):
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_add_and_list_member(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    # admin (DEMO_ADMIN_ID) as the member user
    member_uid = "00000000-0000-0000-0000-000000000010"
    resp = await client.post(f"/api/v1/projects/{proj_id}/members", json={
        "user_id": member_uid, "user_name": "系统管理员",
        "member_role": "delivery", "permission": "edit",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"add member failed: {data}"
    assert data["data"]["member_role"] == "delivery"

    lst = await client.get(f"/api/v1/projects/{proj_id}/members", headers=h)
    assert lst.json()["code"] == 0
    rows = lst.json()["data"]
    assert any(m["user_id"] == member_uid for m in rows)

    # De-dupe: posting same user updates the existing row (still one row)
    resp2 = await client.post(f"/api/v1/projects/{proj_id}/members", json={
        "user_id": member_uid, "member_role": "finance", "permission": "view",
    }, headers=h)
    assert resp2.json()["code"] == 0
    lst2 = await client.get(f"/api/v1/projects/{proj_id}/members", headers=h)
    same_user = [m for m in lst2.json()["data"] if m["user_id"] == member_uid]
    assert len(same_user) == 1, "member should be de-duped per (project, user)"
    assert same_user[0]["member_role"] == "finance"
    assert same_user[0]["permission"] == "view"

    # Update + remove
    mid = same_user[0]["id"]
    upd = await client.put(f"/api/v1/projects/{proj_id}/members/{mid}", json={"permission": "edit"}, headers=h)
    assert upd.json()["code"] == 0 and upd.json()["data"]["permission"] == "edit"
    rm = await client.delete(f"/api/v1/projects/{proj_id}/members/{mid}", headers=h)
    assert rm.json()["code"] == 0

    await _cleanup(client, h, proj_id, cust_id)


async def test_submodule_assignee_roundtrip(client: AsyncClient, auth_headers: dict):
    """A delivery milestone should persist + return its assignee fields."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    resp = await client.post(f"/api/v1/projects/{proj_id}/milestones", json={
        "milestone_code": "ship", "name": "发货",
        "assignee_id": "u-123", "assignee_name": "张三",
        "department_id": "d-1", "department_name": "交付部",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"create milestone failed: {data}"
    ms_id = data["data"]["id"]
    assert data["data"]["assignee_name"] == "张三"
    assert data["data"]["department_name"] == "交付部"

    upd = await client.put(f"/api/v1/milestones/{ms_id}", json={
        "assignee_id": "u-456", "assignee_name": "李四",
    }, headers=h)
    assert upd.json()["code"] == 0
    assert upd.json()["data"]["assignee_name"] == "李四"

    await client.delete(f"/api/v1/milestones/{ms_id}", headers=h)
    await _cleanup(client, h, proj_id, cust_id)


async def test_members_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/projects/fake-id/members")
    assert resp.json()["code"] != 0
