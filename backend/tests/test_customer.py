"""Customer API integration tests."""

from httpx import AsyncClient


async def test_list_customers(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/customers", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]
    assert "total" in data["data"]


async def test_customer_crud(client: AsyncClient, auth_headers: dict):
    # Create
    resp = await client.post("/api/v1/customers", headers=auth_headers, json={
        "name": "测试客户_自动化", "industry": "电子制造", "region": "华东",
    })
    data = resp.json()
    assert data["code"] == 0
    cid = data["data"]["id"]
    assert data["data"]["name"] == "测试客户_自动化"

    # Get
    resp = await client.get(f"/api/v1/customers/{cid}", headers=auth_headers)
    assert resp.json()["code"] == 0

    # Update
    resp = await client.put(f"/api/v1/customers/{cid}", headers=auth_headers, json={
        "name": "测试客户_已更新", "level": "A",
    })
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "测试客户_已更新"

    # Delete
    resp = await client.delete(f"/api/v1/customers/{cid}", headers=auth_headers)
    assert resp.json()["code"] == 0


async def test_customer_export(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/customers/export/excel", headers=auth_headers)
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers.get("content-type", "")


async def test_contact_crud(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/customers", headers=auth_headers, json={"name": "联系人测试客户"})
    cust_id = resp.json()["data"]["id"]

    resp = await client.post(f"/api/v1/customers/{cust_id}/contacts", headers=auth_headers, json={
        "name": "张三", "phone": "13800138000", "is_primary": True,
    })
    assert resp.json()["code"] == 0
    contact_id = resp.json()["data"]["id"]

    resp = await client.get(f"/api/v1/customers/{cust_id}/contacts", headers=auth_headers)
    assert resp.json()["code"] == 0

    await client.delete(f"/api/v1/customers/{cust_id}/contacts/{contact_id}", headers=auth_headers)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=auth_headers)
