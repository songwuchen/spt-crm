"""Activity domain tests — create, list, update, delete activity records."""

from httpx import AsyncClient


async def test_activity_crud(client: AsyncClient, auth_headers: dict):
    """Full CRUD for activity records on a customer."""
    h = auth_headers

    # Create a customer to attach activities to
    cust = await client.post("/api/v1/customers", json={
        "name": "Activity Test Corp", "industry": "Retail", "level": "B",
    }, headers=h)
    assert cust.json()["code"] == 0
    cust_id = cust.json()["data"]["id"]

    # Create activity
    resp = await client.post("/api/v1/activities", json={
        "biz_type": "customer", "biz_id": cust_id,
        "activity_type": "call", "content": "Initial follow-up call",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create activity failed: {data}"
    act_id = data["data"]["id"]

    # List activities for customer
    lst = await client.get("/api/v1/activities", params={
        "biz_type": "customer", "biz_id": cust_id,
    }, headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Update activity
    upd = await client.put(f"/api/v1/activities/{act_id}", json={
        "content": "Follow-up call — very positive",
    }, headers=h)
    assert upd.json()["code"] == 0

    # Delete activity
    dl = await client.delete(f"/api/v1/activities/{act_id}", headers=h)
    assert dl.json()["code"] == 0

    # Cleanup
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_activity_on_project(client: AsyncClient, auth_headers: dict):
    """Activities should work on project biz_type."""
    h = auth_headers

    cust = await client.post("/api/v1/customers", json={
        "name": "Activity Proj Corp", "industry": "IT", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Activity Test Project", "customer_id": cust_id, "stage_code": "S1",
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    # Create activity on project
    resp = await client.post("/api/v1/activities", json={
        "biz_type": "project", "biz_id": proj_id,
        "activity_type": "meeting", "content": "Kick-off meeting",
    }, headers=h)
    assert resp.json()["code"] == 0

    # List
    lst = await client.get("/api/v1/activities", params={
        "biz_type": "project", "biz_id": proj_id,
    }, headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Cleanup
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_activity_no_auth(client: AsyncClient):
    """Activity endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/activities", params={
        "biz_type": "customer", "biz_id": "fake",
    })
    assert resp.json()["code"] != 0
