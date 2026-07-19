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


async def _publish_contract_native_override(client: AsyncClient, h: dict, overrides: list[dict]):
    tpl = (await client.get("/api/v1/lc/entity-templates/contract", headers=h)).json()["data"]
    body = {"field_definitions": overrides, "layout_definition": {}, "rule_definitions": []}
    assert (await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/design",
                              headers=h, json=body)).json()["code"] == 0
    assert (await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/publish",
                              headers=h)).json()["code"] == 0


async def test_masked_contract_amount_cannot_be_overwritten(client: AsyncClient, auth_headers: dict):
    """被脱敏的合同金额不得被写回。

    回归：读取侧把 amount_total 换成 "***"，编辑弹窗把它绑进 InputNumber，用户随手一存
    就会用 null 覆盖真实金额。读取侧脱敏必须与写入侧拦截成对出现。
    """
    h = auth_headers
    cust_id = (await client.post("/api/v1/customers", json={"name": "脱敏合同客户"},
                                 headers=h)).json()["data"]["id"]
    proj_id = (await client.post("/api/v1/projects", json={
        "name": "脱敏合同商机", "customer_id": cust_id, "stage_code": "S1",
    }, headers=h)).json()["data"]["id"]
    contract_id = (await client.post(f"/api/v1/projects/{proj_id}/contracts",
                                     json={"amount_total": 88888}, headers=h)
                   ).json()["data"]["contract"]["id"]

    try:
        await _publish_contract_native_override(client, h, [
            {"id": "amount_total", "native": True, "label": "合同金额", "type": "amount",
             "unmask_roles": ["__finance_only__"]},
        ])

        detail = (await client.get(f"/api/v1/contracts/{contract_id}", headers=h)).json()["data"]
        assert detail["amount_total"] == "***", "读取侧应脱敏"

        # 模拟编辑弹窗把脱敏值原样提交回来
        await client.put(f"/api/v1/contracts/{contract_id}", headers=h, json={"amount_total": None})

        await _publish_contract_native_override(client, h, [])
        after = (await client.get(f"/api/v1/contracts/{contract_id}", headers=h)).json()["data"]
        assert after["amount_total"] == 88888, "脱敏字段的写入必须被丢弃，不得覆盖真实金额"
    finally:
        await _publish_contract_native_override(client, h, [])
        await client.delete(f"/api/v1/contracts/{contract_id}", headers=h)
