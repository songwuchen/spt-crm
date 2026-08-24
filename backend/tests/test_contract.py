"""Contract API integration tests — CRUD + from_quote + signing."""

from httpx import AsyncClient
import datetime


async def test_contract_peek_drawing_no(client: AsyncClient, auth_headers: dict):
    """新建合同登记可预览图纸编号（默认 WMGF）。"""
    r = await client.get("/api/v1/contracts/peek-drawing-no", headers=auth_headers)
    assert r.json()["code"] == 0
    no = (r.json()["data"] or {}).get("drawing_no") or ""
    assert no.startswith("WMGF")
    assert len(no) >= 11


async def test_contract_peek_drawing_no_ignores_order_date(client: AsyncClient, auth_headers: dict):
    """图纸编号年月按取号当天，传订货日也不应落到订货月。"""
    from app.domains.contract.service import drawing_no_apply_date_today

    today = drawing_no_apply_date_today()
    expect_ym = today.strftime("%Y%m")
    r = await client.get(
        "/api/v1/contracts/peek-drawing-no",
        params={"order_date": "2026-07-24", "number_attr": "WMGF"},
        headers=auth_headers,
    )
    assert r.json()["code"] == 0, r.text
    no = (r.json()["data"] or {}).get("drawing_no") or ""
    assert no.startswith(f"WMGF{expect_ym}"), no


async def test_contract_peek_drawing_no_sy(client: AsyncClient, auth_headers: dict):
    """编号属性 SY：预览号按 SY+yy+年序。"""
    r = await client.get(
        "/api/v1/contracts/peek-drawing-no",
        params={"number_attr": "SY"},
        headers=auth_headers,
    )
    assert r.json()["code"] == 0, r.text
    data = r.json()["data"] or {}
    no = data.get("drawing_no") or ""
    assert data.get("number_attr") == "SY"
    assert no.startswith("SY")
    assert len(no) >= 5


async def test_contract_allocate_switches_number_attr(client: AsyncClient, auth_headers: dict):
    """切换编号属性后重新取号：旧前缀号不保留。"""
    h = auth_headers
    peek_w = (await client.get(
        "/api/v1/contracts/peek-drawing-no", params={"number_attr": "WMGF"}, headers=h,
    )).json()["data"]["drawing_no"]
    assert peek_w.startswith("WMGF")
    r = await client.post(
        "/api/v1/contracts/allocate-drawing-no",
        json={"drawing_no": peek_w, "number_attr": "SY"},
        headers=h,
    )
    assert r.json()["code"] == 0, r.text
    next_no = r.json()["data"]["drawing_no"]
    assert next_no.startswith("SY")
    assert next_no != peek_w


async def test_contract_allocate_drawing_no_keeps_available(client: AsyncClient, auth_headers: dict):
    """重新取号：当前号未占用时不空耗号段。"""
    h = auth_headers
    peek = (await client.get("/api/v1/contracts/peek-drawing-no", headers=h)).json()["data"]["drawing_no"]
    r1 = await client.post(
        "/api/v1/contracts/allocate-drawing-no",
        json={"drawing_no": peek},
        headers=h,
    )
    assert r1.json()["code"] == 0, r1.text
    assert r1.json()["data"]["drawing_no"] == peek
    r2 = await client.post(
        "/api/v1/contracts/allocate-drawing-no",
        json={"drawing_no": peek},
        headers=h,
    )
    assert r2.json()["code"] == 0, r2.text
    assert r2.json()["data"]["drawing_no"] == peek
    peek2 = (await client.get("/api/v1/contracts/peek-drawing-no", headers=h)).json()["data"]["drawing_no"]
    assert peek2 == peek


async def test_contract_create_draft_without_required(client: AsyncClient, auth_headers: dict):
    """存草稿：跳过必填；图纸号撞号时报错，不静默换号。"""
    h = auth_headers
    peek = (await client.get("/api/v1/contracts/peek-drawing-no", headers=h)).json()["data"]["drawing_no"]
    body = {
        "as_draft": True,
        "title": "草稿测试",
        "drawing_no": peek,  # 模拟前端把预览号一并提交（不在表内时服务端会补种）
    }
    r1 = await client.post("/api/v1/contracts", json=body, headers=h)
    assert r1.status_code == 200, r1.text
    assert r1.json()["code"] == 0
    c1 = r1.json()["data"]["contract"]
    assert c1["contract_no"].startswith("DRAFT-")
    assert c1["drawing_no"]

    r2 = await client.post("/api/v1/contracts", json=body, headers=h)
    # 业务码 42201；HTTP 可能为 409 Conflict
    assert r2.json()["code"] == 42201, r2.text
    assert "图纸编号" in (r2.json().get("message") or "")
    assert "已用于其他合同登记" in (r2.json().get("message") or "") or "已存在" in (r2.json().get("message") or "")

    # 不传图纸号：草稿允许空号（不再自动取号）
    r3 = await client.post("/api/v1/contracts", json={
        "as_draft": True, "title": "草稿无图纸号",
    }, headers=h)
    assert r3.json()["code"] == 0, r3.text
    c3 = r3.json()["data"]["contract"]
    assert not (c3.get("drawing_no") or "").strip()

    await client.delete(f"/api/v1/contracts/{c1['id']}", headers=h)
    await client.delete(f"/api/v1/contracts/{c3['id']}", headers=h)


async def test_contract_draft_duplicate_contract_no_prompts(client: AsyncClient, auth_headers: dict):
    """存草稿时合同号已存在：提示用户，不静默改号。"""
    h = auth_headers
    no = f"YJ-DRAFT-DUP-{datetime.datetime.now().strftime('%H%M%S%f')}"
    first = await client.post("/api/v1/contracts", json={
        "as_draft": True, "title": "先占号", "contract_no": no,
    }, headers=h)
    assert first.json()["code"] == 0, first.text
    c1 = first.json()["data"]["contract"]
    assert c1["contract_no"] == no

    second = await client.post("/api/v1/contracts", json={
        "as_draft": True, "title": "撞号草稿", "contract_no": no,
    }, headers=h)
    assert second.json()["code"] != 0
    assert "已存在" in (second.json().get("message") or "")

    await client.delete(f"/api/v1/contracts/{c1['id']}", headers=h)


async def test_contract_delete_draft_only(client: AsyncClient, auth_headers: dict):
    """仅草稿可删除；已提交/审批中由后端拦截。"""
    h = auth_headers
    created = await client.post("/api/v1/contracts", json={
        "as_draft": True,
        "title": "待删草稿",
    }, headers=h)
    assert created.json()["code"] == 0, created.text
    cid = created.json()["data"]["contract"]["id"]

    ok = await client.delete(f"/api/v1/contracts/{cid}", headers=h)
    assert ok.json()["code"] == 0

    gone = await client.get(f"/api/v1/contracts/{cid}", headers=h)
    assert gone.json()["code"] != 0


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

    # Create contract（合同号必填，测试显式传入）
    c_resp = await client.post(f"/api/v1/projects/{proj_id}/contracts", json={
        "contract_no": f"CT-TEST-{proj_id[:8].upper()}",
    }, headers=h)
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
                                     json={"contract_no": f"CT-MASK-{proj_id[:8].upper()}", "amount_total": 88888}, headers=h)
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


async def test_contract_customer_id_required(client: AsyncClient, auth_headers: dict):
    """提交合同登记时必须关联客户；存草稿可暂不选。"""
    h = auth_headers
    peek = (await client.get("/api/v1/contracts/peek-drawing-no", headers=h)).json()["data"]["drawing_no"]

    missing = await client.post("/api/v1/contracts", json={
        "title": "缺客户",
        "contract_no": f"CT-NOCUST-{datetime.datetime.now().strftime('%H%M%S%f')}",
        "drawing_no": peek,
        "as_draft": False,
    }, headers=h)
    assert missing.json()["code"] != 0
    assert "关联客户" in (missing.json().get("message") or "")

    draft = await client.post("/api/v1/contracts", json={
        "as_draft": True,
        "title": "草稿可无客户",
    }, headers=h)
    assert draft.json()["code"] == 0, draft.text
    cid = draft.json()["data"]["contract"]["id"]

    blocked = await client.put(f"/api/v1/contracts/{cid}", json={
        "as_draft": False,
        "customer_id": None,
    }, headers=h)
    assert blocked.json()["code"] != 0
    assert "关联客户" in (blocked.json().get("message") or "")

    cust_id = (await client.post("/api/v1/customers", json={
        "name": "合同登记必填客户", "industry": "IT", "level": "B",
    }, headers=h)).json()["data"]["id"]
    ok = await client.put(f"/api/v1/contracts/{cid}", json={
        "as_draft": False,
        "customer_id": cust_id,
    }, headers=h)
    assert ok.json()["code"] == 0, ok.text

    await client.delete(f"/api/v1/contracts/{cid}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_id}", headers=h)


async def test_contract_list_filter_by_customer_name(client: AsyncClient, auth_headers: dict):
    """合同列表支持按客户名称模糊筛选（商机客户 / 直连客户 / 登记 JSON）。"""
    import uuid
    h = auth_headers
    suffix = uuid.uuid4().hex[:10]

    cust_a = (await client.post("/api/v1/customers", json={
        "name": f"筛选客户甲-{suffix}", "industry": "IT", "level": "B",
    }, headers=h)).json()["data"]["id"]
    cust_b = (await client.post("/api/v1/customers", json={
        "name": f"筛选客户乙-{suffix}", "industry": "IT", "level": "B",
    }, headers=h)).json()["data"]["id"]

    proj = (await client.post("/api/v1/projects", json={
        "name": f"筛选商机-{suffix}", "customer_id": cust_a, "stage_code": "S1",
    }, headers=h)).json()["data"]["id"]

    via_proj = (await client.post(f"/api/v1/projects/{proj}/contracts", json={
        "as_draft": True,
        "contract_no": f"CT-FILT-P-{suffix}",
    }, headers=h)).json()["data"]["contract"]["id"]

    via_direct = (await client.post("/api/v1/contracts", json={
        "as_draft": True,
        "contract_no": f"CT-FILT-D-{suffix}",
        "customer_id": cust_b,
    }, headers=h)).json()["data"]["contract"]["id"]

    via_reg = (await client.post("/api/v1/contracts", json={
        "as_draft": True,
        "contract_no": f"CT-FILT-R-{suffix}",
        "registration_json": {"customer_name": f"登记兜底-{suffix}"},
    }, headers=h)).json()["data"]["contract"]["id"]

    hit_a = await client.get("/api/v1/contracts", params={
        "pageNo": 1, "pageSize": 50, "customer_name": f"筛选客户甲-{suffix}",
    }, headers=h)
    assert hit_a.json()["code"] == 0, hit_a.text
    ids_a = {x["id"] for x in hit_a.json()["data"]["items"]}
    assert via_proj in ids_a
    assert via_direct not in ids_a
    assert via_reg not in ids_a

    hit_b = await client.get("/api/v1/contracts", params={
        "pageNo": 1, "pageSize": 50, "customer_name": f"筛选客户乙-{suffix}",
    }, headers=h)
    ids_b = {x["id"] for x in hit_b.json()["data"]["items"]}
    assert via_direct in ids_b
    assert via_proj not in ids_b

    hit_reg = await client.get("/api/v1/contracts", params={
        "pageNo": 1, "pageSize": 50, "customer_name": f"登记兜底-{suffix}",
    }, headers=h)
    ids_reg = {x["id"] for x in hit_reg.json()["data"]["items"]}
    assert via_reg in ids_reg

    for cid in (via_proj, via_direct, via_reg):
        await client.delete(f"/api/v1/contracts/{cid}", headers=h)
    await client.delete(f"/api/v1/projects/{proj}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_a}", headers=h)
    await client.delete(f"/api/v1/customers/{cust_b}", headers=h)
