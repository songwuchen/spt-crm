"""Commission (业务提成) domain tests — calc logic, payouts, rules, summary."""

from httpx import AsyncClient


async def test_commission_calc_and_payout(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    # net = 100000 - (4000+3000+2000+1000)=90000 ; rate 0.05 ; received 50000 -> settle 0.5
    # accrued = 90000 * 0.05 * 0.5 = 2250
    resp = await client.post("/api/v1/commissions", json={
        "customer_name": "提成测试客户", "contract_amount": 100000, "received_amount": 50000,
        "deduction_freight": 4000, "deduction_service": 3000,
        "deduction_entertain": 2000, "deduction_rebate": 1000,
        "commission_rate": 0.05,
    }, headers=h)
    data = resp.json()
    assert data["code"] == 0, f"create commission failed: {data}"
    rec = data["data"]
    cid = rec["id"]
    assert rec["record_no"]
    assert abs(rec["settle_rate"] - 0.5) < 1e-6
    assert abs(rec["accrued_amount"] - 2250.0) < 1e-6
    assert abs(rec["current_amount"] - 2250.0) < 1e-6

    # update received to full -> settle 1.0 -> accrued 4500
    upd = await client.put(f"/api/v1/commissions/{cid}", json={"received_amount": 100000}, headers=h)
    u = upd.json()["data"]
    assert abs(u["settle_rate"] - 1.0) < 1e-6
    assert abs(u["accrued_amount"] - 4500.0) < 1e-6

    # partial payout 2000 -> paid 2000, current 2500, status not paid
    p1 = await client.post(f"/api/v1/commissions/{cid}/payouts", json={"amount": 2000}, headers=h)
    assert p1.json()["code"] == 0
    got = (await client.get(f"/api/v1/commissions/{cid}", headers=h)).json()["data"]
    assert abs(got["paid_amount"] - 2000.0) < 1e-6
    assert abs(got["current_amount"] - 2500.0) < 1e-6
    assert got["status"] != "paid"

    # pay the rest -> status paid
    await client.post(f"/api/v1/commissions/{cid}/payouts", json={"amount": 2500}, headers=h)
    got2 = (await client.get(f"/api/v1/commissions/{cid}", headers=h)).json()["data"]
    assert abs(got2["paid_amount"] - 4500.0) < 1e-6
    assert got2["status"] == "paid"

    payouts = (await client.get(f"/api/v1/commissions/{cid}/payouts", headers=h)).json()["data"]
    assert len(payouts) == 2

    # summary contains our owner row
    summ = (await client.get("/api/v1/commissions/summary", headers=h)).json()
    assert summ["code"] == 0

    # export works
    exp = await client.get("/api/v1/commissions/export/excel", headers=h)
    assert exp.status_code == 200

    await client.delete(f"/api/v1/commissions/{cid}", headers=h)


async def test_commission_rules_crud(client: AsyncClient, auth_headers: dict):
    h = auth_headers
    r = await client.post("/api/v1/commissions/rules", json={
        "name": "默认提成", "scope_type": "all", "rate": 0.03, "min_amount": 10000,
    }, headers=h)
    data = r.json()
    assert data["code"] == 0, f"create rule failed: {data}"
    rid = data["data"]["id"]
    assert abs(data["data"]["rate"] - 0.03) < 1e-6

    lst = (await client.get("/api/v1/commissions/rules", headers=h)).json()
    assert lst["code"] == 0 and any(x["id"] == rid for x in lst["data"])

    upd = await client.put(f"/api/v1/commissions/rules/{rid}", json={"rate": 0.04, "enabled": False}, headers=h)
    assert abs(upd.json()["data"]["rate"] - 0.04) < 1e-6
    assert upd.json()["data"]["enabled"] is False

    dl = await client.delete(f"/api/v1/commissions/rules/{rid}", headers=h)
    assert dl.json()["code"] == 0


async def test_commission_rate_from_rule(client: AsyncClient, auth_headers: dict):
    """When no commission_rate is given, the active 'all' rule's rate is applied."""
    h = auth_headers
    rule = await client.post("/api/v1/commissions/rules", json={
        "name": "通用规则", "scope_type": "all", "rate": 0.02,
    }, headers=h)
    rid = rule.json()["data"]["id"]

    rec = await client.post("/api/v1/commissions", json={
        "customer_name": "规则客户", "contract_amount": 200000, "received_amount": 200000,
    }, headers=h)
    d = rec.json()["data"]
    # net 200000 * 0.02 * 1.0 = 4000
    assert abs(d["commission_rate"] - 0.02) < 1e-6
    assert abs(d["accrued_amount"] - 4000.0) < 1e-6

    await client.delete(f"/api/v1/commissions/{d['id']}", headers=h)
    await client.delete(f"/api/v1/commissions/rules/{rid}", headers=h)


async def test_commission_no_auth(client: AsyncClient):
    assert (await client.get("/api/v1/commissions")).json()["code"] != 0
