"""Solution API integration tests — CRUD + versioning."""

from httpx import AsyncClient


async def test_solution_full_flow(client: AsyncClient, auth_headers: dict):
    """Create project → solution → update → new version → delete."""
    h = auth_headers

    cust = await client.post("/api/v1/customers", json={
        "name": "Solution Test Co", "industry": "IT", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Solution Test Project", "customer_id": cust_id, "stage_code": "S3",
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    # Create solution
    s_resp = await client.post(f"/api/v1/projects/{proj_id}/solutions", json={}, headers=h)
    assert s_resp.json()["code"] == 0
    sol_id = s_resp.json()["data"]["solution"]["id"]
    ver_id = s_resp.json()["data"]["version"]["id"]

    # Get detail
    detail = await client.get(f"/api/v1/solutions/{sol_id}", headers=h)
    assert detail.json()["code"] == 0

    # Update version
    upd = await client.put(f"/api/v1/solution_versions/{ver_id}", json={
        "summary": "Test solution summary",
        "config_json": {"items": [{"item": "Server", "qty": 2}]},
        "risk_list_json": {"risks": [{"risk": "Schedule delay", "level": "M"}]},
    }, headers=h)
    assert upd.json()["code"] == 0

    # New version (returns flat version object)
    nv = await client.post(f"/api/v1/solutions/{sol_id}/new_version", headers=h)
    assert nv.json()["code"] == 0
    v2 = nv.json()["data"]
    assert v2["version_no"] == 2

    # List solutions for project
    lst = await client.get(f"/api/v1/projects/{proj_id}/solutions", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Delete
    d_resp = await client.delete(f"/api/v1/solutions/{sol_id}", headers=h)
    assert d_resp.json()["code"] == 0

    # Cleanup
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)
