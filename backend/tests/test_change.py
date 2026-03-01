"""Change request domain tests — CRUD + status transitions."""

from httpx import AsyncClient


async def _setup_project(client: AsyncClient, h: dict) -> tuple[str, str]:
    cust = await client.post("/api/v1/customers", json={
        "name": "Change Test Corp", "industry": "Technology", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Change Test Project", "customer_id": cust_id,
        "stage_code": "S1", "amount_expect": 150000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]
    return cust_id, proj_id


async def _cleanup(client: AsyncClient, h: dict, proj_id: str, cust_id: str):
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_change_request_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, get, update, delete change requests."""
    h = auth_headers
    cust_id, proj_id = await _setup_project(client, h)

    # Create change request
    resp = await client.post(f"/api/v1/projects/{proj_id}/change_requests", json={
        "change_type": "scope",
        "reason": "Customer requested additional features",
        "impact_json": {"cost": "+20000", "timeline": "+2 weeks"},
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Create CR failed: {data}"
    cr_id = data["data"]["id"]

    # List change requests
    lst = await client.get(f"/api/v1/projects/{proj_id}/change_requests", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Get detail
    detail = await client.get(f"/api/v1/change_requests/{cr_id}", headers=h)
    assert detail.json()["code"] == 0
    assert detail.json()["data"]["change_type"] == "scope"

    # Update: draft → reviewing
    upd = await client.put(f"/api/v1/change_requests/{cr_id}", json={
        "status": "reviewing",
    }, headers=h)
    assert upd.json()["code"] == 0

    # Update: reviewing → approved
    upd2 = await client.put(f"/api/v1/change_requests/{cr_id}", json={
        "status": "approved",
        "to_version_ref_json": {"quote_v2": True},
    }, headers=h)
    assert upd2.json()["code"] == 0

    # Delete
    dl = await client.delete(f"/api/v1/change_requests/{cr_id}", headers=h)
    assert dl.json()["code"] == 0

    await _cleanup(client, h, proj_id, cust_id)


async def test_change_request_no_auth(client: AsyncClient):
    """Change request endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/projects/fake-id/change_requests")
    assert resp.json()["code"] != 0
