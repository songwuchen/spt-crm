"""Change request impact estimation + status transition edge cases."""

from httpx import AsyncClient


async def _setup(client: AsyncClient, h: dict) -> tuple[str, str, str]:
    cust = await client.post("/api/v1/customers", json={
        "name": "Impact Test Corp", "industry": "Manufacturing", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Impact Test Project", "customer_id": cust_id,
        "stage_code": "S3", "amount_expect": 500000,
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    # Create milestones for the project
    for code, name, order in [("design", "Design", 1), ("procure", "Procurement", 2), ("install", "Install", 3)]:
        await client.post(f"/api/v1/projects/{proj_id}/milestones", json={
            "milestone_code": code, "name": name, "plan_date": "2026-08-01", "sort_order": order,
        }, headers=h)

    # Create a change request
    cr = await client.post(f"/api/v1/projects/{proj_id}/change_requests", json={
        "change_type": "delivery", "reason": "Customer scope change",
    }, headers=h)
    cr_id = cr.json()["data"]["id"]
    return cust_id, proj_id, cr_id


async def _cleanup(client: AsyncClient, h: dict, proj_id: str, cust_id: str):
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_estimate_impact(client: AsyncClient, auth_headers: dict):
    """Estimate impact should return affected milestones and risk summary."""
    h = auth_headers
    cust_id, proj_id, cr_id = await _setup(client, h)

    resp = await client.post(f"/api/v1/change_requests/{cr_id}/estimate_impact", headers=h)
    data = resp.json()
    assert data["code"] == 0, f"Estimate impact failed: {data}"
    impact = data["data"]
    assert "affected_milestones" in impact
    assert "affected_milestone_count" in impact
    assert "total_milestone_count" in impact
    assert impact["total_milestone_count"] == 3
    assert isinstance(impact["risk_summary"], list)

    await _cleanup(client, h, proj_id, cust_id)


async def test_invalid_status_transition(client: AsyncClient, auth_headers: dict):
    """Status transition from draft directly to approved should fail."""
    h = auth_headers
    cust_id, proj_id, cr_id = await _setup(client, h)

    resp = await client.put(f"/api/v1/change_requests/{cr_id}", json={
        "status": "approved",
    }, headers=h)
    data = resp.json()
    assert data["code"] != 0, "Should reject invalid transition draft→approved"

    await _cleanup(client, h, proj_id, cust_id)


async def test_change_not_found(client: AsyncClient, auth_headers: dict):
    """Access non-existent change request should return NOT_FOUND."""
    resp = await client.get("/api/v1/change_requests/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.json()["code"] != 0
