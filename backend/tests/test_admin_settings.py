"""Admin settings tests — features, integrations, webhooks."""

from httpx import AsyncClient


async def test_feature_toggle_upsert(client: AsyncClient, auth_headers: dict):
    """Create and toggle a feature flag."""
    h = auth_headers

    # Upsert feature: disable ai_center
    resp = await client.put("/api/admin/v1/tenant/features/ai_center", json={
        "enabled": False,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0

    # List features
    lst = await client.get("/api/admin/v1/tenant/features", headers=h)
    assert lst.json()["code"] == 0
    feature = next((f for f in lst.json()["data"] if f["feature_code"] == "ai_center"), None)
    assert feature is not None
    assert feature["enabled"] is False

    # Re-enable
    await client.put("/api/admin/v1/tenant/features/ai_center", json={"enabled": True}, headers=h)


async def test_integration_endpoint_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, update, delete integration endpoints."""
    h = auth_headers

    # Create
    resp = await client.post("/api/admin/v1/tenant/integrations", json={
        "system_code": "test_erp",
        "name": "Test ERP",
        "base_url": "https://erp.example.com/api",
        "auth_type": "apikey",
        "auth_config_json": {"api_key": "sk-test-123"},
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0
    ep_id = data["data"]["id"]

    # List — should NOT expose auth_config_json
    lst = await client.get("/api/admin/v1/tenant/integrations", headers=h)
    assert lst.json()["code"] == 0
    for item in lst.json()["data"]:
        assert "auth_config_json" not in item

    # Update
    upd = await client.put(f"/api/admin/v1/tenant/integrations/{ep_id}", json={
        "status": "inactive",
    }, headers=h)
    assert upd.json()["code"] == 0

    # Delete
    dl = await client.delete(f"/api/admin/v1/tenant/integrations/{ep_id}", headers=h)
    assert dl.json()["code"] == 0


async def test_webhook_subscription_crud(client: AsyncClient, auth_headers: dict):
    """Create, list, delete webhook subscriptions."""
    h = auth_headers

    resp = await client.post("/api/admin/v1/tenant/webhooks", json={
        "event_types_json": ["project.stage_changed", "contract.signed"],
        "target_url": "https://hooks.example.com/crm",
        "secret_token": "whsec_test_token",
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0
    ws_id = data["data"]["id"]

    lst = await client.get("/api/admin/v1/tenant/webhooks", headers=h)
    assert lst.json()["code"] == 0
    assert any(w["id"] == ws_id for w in lst.json()["data"])

    dl = await client.delete(f"/api/admin/v1/tenant/webhooks/{ws_id}", headers=h)
    assert dl.json()["code"] == 0


async def test_dashboard_trend(client: AsyncClient, auth_headers: dict):
    """Dashboard trend endpoint returns monthly data."""
    resp = await client.get("/api/v1/dashboard/trend?months=6", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


async def test_dashboard_collection(client: AsyncClient, auth_headers: dict):
    """Dashboard collection endpoint returns monthly data."""
    resp = await client.get("/api/v1/dashboard/collection?months=6", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
