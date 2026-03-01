"""End-to-end business flow test:
Customer → Project → Quote → Contract → Sign → Stage Advance
"""

from httpx import AsyncClient
import datetime


async def test_full_business_flow(client: AsyncClient, auth_headers: dict):
    """Complete CRM business cycle with force-advance."""
    h = auth_headers
    today = datetime.date.today().isoformat()

    # 1. Create customer
    cust = await client.post("/api/v1/customers", json={
        "name": "E2E Test Corp", "industry": "Manufacturing", "level": "A",
    }, headers=h)
    assert cust.json()["code"] == 0
    cust_id = cust.json()["data"]["id"]

    # 2. Create project at S1
    proj = await client.post("/api/v1/projects", json={
        "name": "E2E Big Deal", "customer_id": cust_id, "stage_code": "S1",
        "amount_expect": 500000,
    }, headers=h)
    assert proj.json()["code"] == 0
    proj_id = proj.json()["data"]["id"]

    # 3. Force advance S1 → S2 → S3
    adv = await client.post(f"/api/v1/projects/{proj_id}/advance", json={
        "to_stage": "S2", "force": True,
    }, headers=h)
    assert adv.json()["code"] == 0
    assert adv.json()["data"]["stage_code"] == "S2"

    adv = await client.post(f"/api/v1/projects/{proj_id}/advance", json={
        "to_stage": "S3", "force": True,
    }, headers=h)
    assert adv.json()["code"] == 0
    assert adv.json()["data"]["stage_code"] == "S3"

    # 4. Create quote
    q = await client.post(f"/api/v1/projects/{proj_id}/quotes", json={}, headers=h)
    assert q.json()["code"] == 0
    quote_id = q.json()["data"]["quote"]["id"]
    ver_id = q.json()["data"]["version"]["id"]

    # 5. Add line items
    await client.post(f"/api/v1/quote_versions/{ver_id}/lines", json={
        "product_name": "CRM System", "quantity": 1, "unit_price": 300000,
    }, headers=h)
    await client.post(f"/api/v1/quote_versions/{ver_id}/lines", json={
        "product_name": "Implementation", "quantity": 1, "unit_price": 200000,
    }, headers=h)

    # 6. Convert quote to contract
    ct = await client.post("/api/v1/contracts/from_quote", json={
        "quote_id": quote_id,
    }, headers=h)
    assert ct.json()["code"] == 0
    contract_id = ct.json()["data"]["contract"]["id"]

    # 7. Sign contract
    sign = await client.post(f"/api/v1/contracts/{contract_id}/sign", json={
        "signed_date": today,
    }, headers=h)
    assert sign.json()["code"] == 0
    assert sign.json()["data"]["status"] == "signed"

    # 8. Force advance S3 → S4
    adv = await client.post(f"/api/v1/projects/{proj_id}/advance", json={
        "to_stage": "S4", "force": True,
    }, headers=h)
    assert adv.json()["code"] == 0
    assert adv.json()["data"]["stage_code"] == "S4"

    # 9. Verify customer stats
    stats = await client.get(f"/api/v1/customers/{cust_id}/stats", headers=h)
    assert stats.json()["code"] == 0
    assert stats.json()["data"]["project_count"] >= 1

    # 10. Dashboard stats
    dashboard = await client.get("/api/v1/dashboard/stats", headers=h)
    assert dashboard.json()["code"] == 0
    assert dashboard.json()["data"]["project_total"] >= 1

    # 11. Notifications generated
    notifs = await client.get("/api/v1/notifications", headers=h)
    assert notifs.json()["code"] == 0

    # 12. Analytics endpoints
    for endpoint in ["funnel", "win_loss", "top_customers", "leaderboard"]:
        resp = await client.get(f"/api/v1/dashboard/{endpoint}", headers=h)
        assert resp.json()["code"] == 0

    # Cleanup
    await client.delete(f"/api/v1/contracts/{contract_id}", headers=h)
    await client.delete(f"/api/v1/quotes/{quote_id}", headers=h)
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_permission_boundary(client: AsyncClient):
    """Unauthenticated requests should be rejected."""
    endpoints = [
        ("GET", "/api/v1/customers"),
        ("GET", "/api/v1/projects"),
        ("GET", "/api/v1/dashboard/stats"),
        ("GET", "/api/v1/notifications"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path)
        data = resp.json()
        assert data["code"] != 0, f"{method} {path} should require auth"


async def test_health_endpoints(client: AsyncClient):
    """Health check endpoints should work without auth."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp2 = await client.get("/health/ready")
    assert resp2.status_code == 200
    assert resp2.json()["db"] == "connected"
