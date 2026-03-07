"""Product & Renewal API integration tests."""

import pytest
from httpx import AsyncClient


async def _has_product_permission(client: AsyncClient, auth_headers: dict) -> bool:
    resp = await client.get("/api/v1/products", headers=auth_headers)
    return resp.json().get("code") == 0


async def test_list_products(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/products", headers=auth_headers)
    data = resp.json()
    if data["code"] == 40300:
        pytest.skip("Admin user lacks product:view permission in test DB")
    assert data["code"] == 0
    assert "items" in data["data"]
    assert isinstance(data["data"]["items"], list)


async def test_product_crud(client: AsyncClient, auth_headers: dict):
    if not await _has_product_permission(client, auth_headers):
        pytest.skip("Admin user lacks product permissions in test DB")
    # Create
    resp = await client.post("/api/v1/products", headers=auth_headers, json={
        "product_code": "TEST-P001",
        "name": "测试产品",
        "item_type": "standard",
        "unit": "台",
        "unit_price": 9999.99,
        "cost_price": 5000.00,
        "leadtime_days": 14,
        "is_active": True,
    })
    data = resp.json()
    assert data["code"] == 0
    pid = data["data"]["id"]
    assert data["data"]["product_code"] == "TEST-P001"
    assert data["data"]["unit_price"] == 9999.99

    # Read
    resp = await client.get(f"/api/v1/products/{pid}", headers=auth_headers)
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["name"] == "测试产品"

    # Update
    resp = await client.put(f"/api/v1/products/{pid}", headers=auth_headers, json={
        "name": "测试产品-更新",
        "unit_price": 12000.00,
        "is_active": False,
    })
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["name"] == "测试产品-更新"
    assert resp.json()["data"]["is_active"] is False

    # Delete
    resp = await client.delete(f"/api/v1/products/{pid}", headers=auth_headers)
    assert resp.json()["code"] == 0


async def test_product_search(client: AsyncClient, auth_headers: dict):
    if not await _has_product_permission(client, auth_headers):
        pytest.skip("Admin user lacks product permissions in test DB")
    # Create two products
    await client.post("/api/v1/products", headers=auth_headers, json={
        "product_code": "SRCH-001", "name": "搜索测试Alpha", "is_active": True,
    })
    await client.post("/api/v1/products", headers=auth_headers, json={
        "product_code": "SRCH-002", "name": "搜索测试Beta", "is_active": True,
    })

    # Search by keyword
    resp = await client.get("/api/v1/products", headers=auth_headers, params={"keyword": "Alpha"})
    data = resp.json()
    assert data["code"] == 0
    assert any("Alpha" in p["name"] for p in data["data"]["items"])


async def test_product_usage_count(client: AsyncClient, auth_headers: dict):
    """Products list should include usage_count field."""
    if not await _has_product_permission(client, auth_headers):
        pytest.skip("Admin user lacks product permissions in test DB")
    resp = await client.get("/api/v1/products", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    for item in data["data"]["items"]:
        assert "usage_count" in item
        assert isinstance(item["usage_count"], int)


async def test_category_crud(client: AsyncClient, auth_headers: dict):
    if not await _has_product_permission(client, auth_headers):
        pytest.skip("Admin user lacks product permissions in test DB")
    # Create
    resp = await client.post("/api/v1/products/categories", headers=auth_headers, json={
        "name": "测试分类",
        "description": "用于测试",
        "sort_order": 1,
    })
    data = resp.json()
    assert data["code"] == 0
    cid = data["data"]["id"]

    # Create child category
    resp = await client.post("/api/v1/products/categories", headers=auth_headers, json={
        "name": "子分类",
        "parent_id": cid,
        "sort_order": 2,
    })
    assert resp.json()["code"] == 0
    child_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["parent_id"] == cid

    # List
    resp = await client.get("/api/v1/products/categories", headers=auth_headers)
    assert resp.json()["code"] == 0
    cats = resp.json()["data"]
    assert any(c["id"] == cid for c in cats)

    # Update
    resp = await client.put(f"/api/v1/products/categories/{cid}", headers=auth_headers, json={
        "name": "测试分类-更新",
    })
    assert resp.json()["code"] == 0

    # Delete child first, then parent
    resp = await client.delete(f"/api/v1/products/categories/{child_id}", headers=auth_headers)
    assert resp.json()["code"] == 0
    resp = await client.delete(f"/api/v1/products/categories/{cid}", headers=auth_headers)
    assert resp.json()["code"] == 0


async def test_renewal_with_customer_name(client: AsyncClient, auth_headers: dict):
    """Renewal list should include customer_name."""
    resp = await client.post("/api/v1/customers", headers=auth_headers, json={"name": "续约客户名测试"})
    cust_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/renewal_opportunities", headers=auth_headers, json={
        "customer_id": cust_id, "name": "测试续约名称", "amount_expect": 50000,
    })
    assert resp.json()["code"] == 0

    # List and check customer_name
    resp = await client.get("/api/v1/renewal_opportunities", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    found = [r for r in data["data"] if r["name"] == "测试续约名称"]
    assert len(found) > 0
    assert found[0]["customer_name"] == "续约客户名测试"

    # Cleanup
    await client.delete(f"/api/v1/customers/{cust_id}", headers=auth_headers)


async def test_renewal_status_filter(client: AsyncClient, auth_headers: dict):
    """Renewal list supports status filter."""
    resp = await client.get("/api/v1/renewal_opportunities", headers=auth_headers, params={"status": "won"})
    data = resp.json()
    assert data["code"] == 0
    for r in data["data"]:
        assert r["status"] == "won"
