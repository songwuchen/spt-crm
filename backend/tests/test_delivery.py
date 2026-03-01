"""Delivery domain tests — ERP order links and milestones."""

from httpx import AsyncClient


async def _setup_project(client: AsyncClient, h: dict) -> tuple[str, str]:
    cust = await client.post("/api/v1/customers", json={
        "name": "Delivery Test Corp", "industry": "Manufacturing", "level": "B",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Delivery Test Project", "customer_id": cust_id,
        "stage_code": "S1", "amount_expect": 200000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]
    return cust_id, proj_id


async def _cleanup(client: AsyncClient, h: dict, proj_id: str, cust_id: str):
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_erp_order_link_flow(client: AsyncClient, auth_headers: dict):
    """Create, list, delete ERP order links."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    # Create order link
    resp = await client.post(f"/api/v1/projects/{proj_id}/order_links", json={
        "erp_system_code": "SAP", "erp_order_no": "SO-2026-001",
        "remark": "Main order",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create order link failed: {data}"
    link_id = data["data"]["id"]

    # List order links
    lst = await client.get(f"/api/v1/projects/{proj_id}/order_links", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Delete order link
    dl = await client.delete(f"/api/v1/order_links/{link_id}", headers=h)
    assert dl.json()["code"] == 0

    await _cleanup(client, h, proj_id, cust_id)


async def test_milestone_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, get, update, delete milestones."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    # Create milestone
    resp = await client.post(f"/api/v1/projects/{proj_id}/milestones", json={
        "milestone_code": "FAT", "name": "Factory Acceptance Test",
        "plan_date": "2026-06-15", "sort_order": 1,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create milestone failed: {data}"
    ms_id = data["data"]["id"]

    # List milestones
    lst = await client.get(f"/api/v1/projects/{proj_id}/milestones", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Get milestone detail
    detail = await client.get(f"/api/v1/milestones/{ms_id}", headers=h)
    assert detail.json()["code"] == 0
    assert detail.json()["data"]["milestone_code"] == "FAT"

    # Update milestone
    upd = await client.put(f"/api/v1/milestones/{ms_id}", json={
        "actual_date": "2026-06-20", "status": "completed",
    }, headers=h)
    assert upd.json()["code"] == 0

    # Delete milestone
    dl = await client.delete(f"/api/v1/milestones/{ms_id}", headers=h)
    assert dl.json()["code"] == 0

    await _cleanup(client, h, proj_id, cust_id)


async def test_milestone_no_auth(client: AsyncClient):
    """Milestone endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/projects/fake-id/milestones")
    assert resp.json()["code"] != 0
