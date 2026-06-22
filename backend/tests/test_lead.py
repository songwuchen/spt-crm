"""Lead API integration tests."""

from httpx import AsyncClient


async def test_list_leads(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/leads", headers=auth_headers)
    data = resp.json()
    assert data["code"] == 0
    assert "items" in data["data"]


async def test_lead_crud(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/leads", headers=auth_headers, json={
        "title": "测试线索_自动化", "company_name": "测试公司", "source": "website",
    })
    data = resp.json()
    assert data["code"] == 0
    lid = data["data"]["id"]
    assert data["data"]["lead_code"] is not None

    resp = await client.get(f"/api/v1/leads/{lid}", headers=auth_headers)
    assert resp.json()["code"] == 0

    resp = await client.put(f"/api/v1/leads/{lid}", headers=auth_headers, json={
        "title": "测试线索_已更新", "score": 80,
    })
    assert resp.json()["code"] == 0

    await client.delete(f"/api/v1/leads/{lid}", headers=auth_headers)


async def test_lead_export(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/leads/export/excel", headers=auth_headers)
    assert resp.status_code == 200


async def test_qualify_creates_customer_only_by_default(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "仅转客户线索", "company_name": "仅客户公司", "source": "website",
    })).json()["data"]["id"]
    res = (await client.post(f"/api/v1/leads/{lid}/qualify", headers=h)).json()
    assert res["code"] == 0
    assert res["data"]["customer_id"]
    assert res["data"].get("project_id") is None  # 默认不建商机


async def test_qualify_with_create_opportunity_carries_context(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "大型振动筛采购", "company_name": "矿业集团",
        "source": "expo", "demand_summary": "需要 3 台大型直线振动筛，含保函",
        "budget_range": "200-300万",
    })).json()["data"]["id"]

    res = (await client.post(f"/api/v1/leads/{lid}/qualify", headers=h,
                             json={"create_opportunity": True})).json()
    assert res["code"] == 0
    cid = res["data"]["customer_id"]
    pid = res["data"].get("project_id")
    assert pid, "勾选后应创建商机"
    assert res["data"].get("project_code")

    # 商机应关联到新客户，并带入需求摘要
    proj = (await client.get(f"/api/v1/projects/{pid}", headers=h)).json()["data"]
    assert proj["customer_id"] == cid
    assert proj["stage_code"] == "S1"
    assert (proj.get("key_requirements_json") or {}).get("summary") == "需要 3 台大型直线振动筛，含保函"

    await client.delete(f"/api/v1/projects/{pid}", headers=h)
    await client.delete(f"/api/v1/customers/{cid}", headers=h)
