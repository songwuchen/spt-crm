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


async def test_lead_custom_fields_survive_read_and_edit(client: AsyncClient, auth_headers: dict):
    """扩展字段值必须出现在出参里，且不被「不带该字段的更新」清空。

    回归：_lead_dict 曾漏掉 custom_fields_json，前端编辑表单读到空对象后原样回提，
    每次保存都会静默清空已存的扩展字段值。
    """
    h = auth_headers
    cf = {"f_industry_note": "选矿", "f_visit_count": 3}
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "扩展字段线索", "company_name": "扩展字段公司", "custom_fields_json": cf,
    })).json()["data"]["id"]

    # 详情与列表都应回传扩展字段值
    detail = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert detail["custom_fields_json"] == cf

    listed = (await client.get("/api/v1/leads", headers=h,
                               params={"keyword": "扩展字段线索"})).json()["data"]["items"]
    assert any(i["id"] == lid and i["custom_fields_json"] == cf for i in listed)

    # 不携带 custom_fields_json 的更新不应清空已存值
    await client.put(f"/api/v1/leads/{lid}", headers=h, json={"title": "扩展字段线索_改名"})
    after = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert after["custom_fields_json"] == cf

    await client.delete(f"/api/v1/leads/{lid}", headers=h)


async def test_lead_date_field_filter(client: AsyncClient, auth_headers: dict):
    """日期区间可切换按 biz_date 筛选（默认仍按 created_at）。"""
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "业务日期线索", "company_name": "业务日期公司", "biz_date": "2020-03-15",
    })).json()["data"]["id"]

    def ids(items):
        return [i["id"] for i in items]

    hit = (await client.get("/api/v1/leads", headers=h, params={
        "date_field": "biz_date", "start_date": "2020-03-01", "end_date": "2020-03-31",
    })).json()["data"]["items"]
    assert lid in ids(hit)

    miss = (await client.get("/api/v1/leads", headers=h, params={
        "date_field": "biz_date", "start_date": "2020-04-01", "end_date": "2020-04-30",
    })).json()["data"]["items"]
    assert lid not in ids(miss)

    # 默认维度仍是 created_at：按 2020 年筛创建时间应筛不到今天刚建的这条
    default_dim = (await client.get("/api/v1/leads", headers=h, params={
        "start_date": "2020-03-01", "end_date": "2020-03-31",
    })).json()["data"]["items"]
    assert lid not in ids(default_dim)

    await client.delete(f"/api/v1/leads/{lid}", headers=h)


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
