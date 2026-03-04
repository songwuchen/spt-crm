"""Audit log integrity + export tests."""

from httpx import AsyncClient


async def test_audit_log_list(client: AsyncClient, auth_headers: dict):
    """List audit logs with pagination."""
    h = auth_headers

    # Perform an action to generate an audit log
    cust = await client.post("/api/v1/customers", json={
        "name": "Audit Test Corp", "industry": "Tech", "level": "B",
    }, headers=h)
    cust_id = cust.json()["data"]["id"]

    # Query audit logs
    resp = await client.get("/api/v1/audit_logs?pageNo=1&pageSize=5", headers=h)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]
    assert "total" in data["data"]
    assert len(data["data"]["items"]) <= 5

    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_audit_log_filter(client: AsyncClient, auth_headers: dict):
    """Filter audit logs by resource_type."""
    h = auth_headers
    resp = await client.get("/api/v1/audit_logs?resource_type=customer", headers=h)
    data = resp.json()
    assert data["code"] == 0
    for item in data["data"]["items"]:
        assert item["resource_type"] == "customer"


async def test_audit_log_export(client: AsyncClient, auth_headers: dict):
    """Export audit logs as Excel should return xlsx."""
    h = auth_headers
    resp = await client.get("/api/v1/audit_logs/export", headers=h)
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers.get("content-type", "")


async def test_audit_log_verify(client: AsyncClient, auth_headers: dict):
    """Verify audit log integrity — tamper-proof hash check."""
    h = auth_headers
    resp = await client.post("/api/v1/audit_logs/verify", headers=h)
    data = resp.json()
    assert data["code"] == 0
    result = data["data"]
    assert "total_checked" in result
    assert "tampered_count" in result
    assert result["tampered_count"] == 0  # No tampered records expected


async def test_audit_no_auth(client: AsyncClient):
    """Audit endpoints should reject unauthenticated requests."""
    resp = await client.get("/api/v1/audit_logs")
    assert resp.json()["code"] != 0
