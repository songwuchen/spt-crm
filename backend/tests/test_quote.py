"""Quote API integration tests — CRUD + versioning + line items."""

from httpx import AsyncClient


async def test_create_quote_no_auth(client: AsyncClient):
    """Creating quote without auth should be rejected."""
    resp = await client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000099/quotes",
        json={},
    )
    data = resp.json()
    assert data["code"] != 0


async def test_quote_full_flow(client: AsyncClient, auth_headers: dict):
    """Create project → create quote → add line → new version → list."""
    h = auth_headers

    cust = await client.post("/api/v1/customers", json={
        "name": "Quote Test Customer", "industry": "IT", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Quote Test Project", "customer_id": cust_id, "stage_code": "S1",
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    # Create quote
    q_resp = await client.post(f"/api/v1/projects/{proj_id}/quotes", json={}, headers=h)
    q_data = q_resp.json()
    assert q_data["code"] == 0
    quote_id = q_data["data"]["quote"]["id"]
    version_id = q_data["data"]["version"]["id"]

    # Add line item
    line_resp = await client.post(f"/api/v1/quote_versions/{version_id}/lines", json={
        "item_name": "CRM License", "qty": 10, "unit_price": 5000,
    }, headers=h)
    assert line_resp.json()["code"] == 0

    # Get quote detail (returns flat object with id, versions, lines, etc.)
    detail = await client.get(f"/api/v1/quotes/{quote_id}", headers=h)
    assert detail.json()["code"] == 0
    assert detail.json()["data"]["id"] == quote_id
    assert "versions" in detail.json()["data"]

    # New version (returns flat version object)
    nv = await client.post(f"/api/v1/quotes/{quote_id}/new_version", headers=h)
    assert nv.json()["code"] == 0
    assert nv.json()["data"]["version_no"] == 2

    # List project quotes
    lst = await client.get(f"/api/v1/projects/{proj_id}/quotes", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Cleanup
    await client.delete(f"/api/v1/quotes/{quote_id}", headers=h)
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)
