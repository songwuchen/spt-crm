"""Contract API integration tests — CRUD + from_quote + signing."""

from httpx import AsyncClient
import datetime


async def test_contract_full_flow(client: AsyncClient, auth_headers: dict):
    """Create project → contract → version → sign → list."""
    h = auth_headers
    today = datetime.date.today().isoformat()

    cust = await client.post("/api/v1/customers", json={
        "name": "Contract Test Co", "industry": "IT", "level": "B",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "Contract Test Project", "customer_id": cust_id, "stage_code": "S1",
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    # Create contract
    c_resp = await client.post(f"/api/v1/projects/{proj_id}/contracts", json={}, headers=h)
    assert c_resp.json()["code"] == 0
    contract_id = c_resp.json()["data"]["contract"]["id"]
    ver_id = c_resp.json()["data"]["version"]["id"]

    # Get contract detail
    detail = await client.get(f"/api/v1/contracts/{contract_id}", headers=h)
    assert detail.json()["code"] == 0

    # Update version
    upd = await client.put(f"/api/v1/contract_versions/{ver_id}", json={
        "terms_text": "Test terms content",
    }, headers=h)
    assert upd.json()["code"] == 0

    # Sign contract
    sign = await client.post(f"/api/v1/contracts/{contract_id}/sign", json={
        "signed_date": today,
    }, headers=h)
    assert sign.json()["code"] == 0
    assert sign.json()["data"]["status"] == "signed"

    # List project contracts
    lst = await client.get(f"/api/v1/projects/{proj_id}/contracts", headers=h)
    assert lst.json()["code"] == 0
    assert len(lst.json()["data"]) >= 1

    # Cleanup
    await client.delete(f"/api/v1/contracts/{contract_id}", headers=h)
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_contract_from_quote(client: AsyncClient, auth_headers: dict):
    """Quote → Contract conversion."""
    h = auth_headers

    cust = await client.post("/api/v1/customers", json={
        "name": "FromQuote Co", "industry": "IT", "level": "A",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    proj = await client.post("/api/v1/projects", json={
        "name": "FromQuote Project", "customer_id": cust_id, "stage_code": "S3",
    }, headers=h)
    proj_id = proj.json()["data"]["id"]

    # Create quote
    q = await client.post(f"/api/v1/projects/{proj_id}/quotes", json={}, headers=h)
    quote_id = q.json()["data"]["quote"]["id"]

    # Convert to contract
    c = await client.post("/api/v1/contracts/from_quote", json={
        "quote_id": quote_id,
    }, headers=h)
    assert c.json()["code"] == 0
    contract = c.json()["data"]["contract"]
    assert contract["from_quote_id"] == quote_id

    # Cleanup
    await client.delete(f"/api/v1/contracts/{contract['id']}", headers=h)
    await client.delete(f"/api/v1/quotes/{quote_id}", headers=h)
    await client.delete(f"/api/v1/projects/{proj_id}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)
