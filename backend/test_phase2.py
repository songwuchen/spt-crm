"""End-to-end verification for Phase 2: Project + Quote + Contract"""
import requests
import json

BASE = "http://localhost:8002"

def pp(label, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    if isinstance(data, dict):
        print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
    else:
        print(data)

# Login
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
token = r.json()["data"]["access_token"]
h = {"Authorization": f"Bearer {token}"}
print("Login OK")

# === 1. Create Project ===
r = requests.post(f"{BASE}/api/v1/projects", json={
    "name": "智能制造产线升级项目", "amount_expect": 800000, "probability": 65, "risk_level": "M"
}, headers=h)
d = r.json()
assert d["code"] == 0, f"Create project failed: {d}"
pid = d["data"]["id"]
pp("1. Create Project", d["data"])
print(f"  -> Project ID: {pid}")
print(f"  -> Code: {d['data']['project_code']}, Stage: {d['data']['stage_code']}")

# === 2. Advance S1 -> S2 ===
r = requests.post(f"{BASE}/api/v1/projects/{pid}/advance", json={"to_stage": "S2", "note": "需求已确认"}, headers=h)
d = r.json()
assert d["code"] == 0 and d["data"]["stage_code"] == "S2"
pp("2. Advance S1->S2", f"Stage: {d['data']['stage_code']}")

# === 3. Advance S2 -> S3 ===
r = requests.post(f"{BASE}/api/v1/projects/{pid}/advance", json={"to_stage": "S3", "note": "进入方案报价阶段"}, headers=h)
d = r.json()
assert d["code"] == 0 and d["data"]["stage_code"] == "S3"
pp("3. Advance S2->S3", f"Stage: {d['data']['stage_code']}")

# === 4. Stage History ===
r = requests.get(f"{BASE}/api/v1/projects/{pid}/stage_history", headers=h)
d = r.json()
assert d["code"] == 0 and len(d["data"]) == 2
pp("4. Stage History", f"{len(d['data'])} records")
for hist in d["data"]:
    print(f"  {hist['from_stage']} -> {hist['to_stage']} | {hist['note']} | by {hist['changed_by_name']}")

# === 5. Create Quote under project ===
r = requests.post(f"{BASE}/api/v1/projects/{pid}/quotes", json={"title": "首次报价"}, headers=h)
d = r.json()
assert d["code"] == 0
qid = d["data"]["quote"]["id"]
vid = d["data"]["version"]["id"]
pp("5. Create Quote", f"Quote ID: {qid[:8]}..., Version: V{d['data']['version']['version_no']}")

# === 6. Add line items ===
lines_data = [
    {"item_name": "伺服电机", "item_type": "standard", "item_code": "SRV-001", "qty": 10, "unit": "台", "unit_price": 5000, "cost_est": 3000, "leadtime_days": 30},
    {"item_name": "PLC控制器", "item_type": "standard", "item_code": "PLC-002", "qty": 5, "unit": "套", "unit_price": 12000, "cost_est": 8000, "leadtime_days": 45},
    {"item_name": "现场安装调试", "item_type": "service", "qty": 1, "unit": "项", "unit_price": 20000, "cost_est": 15000, "leadtime_days": 15},
]
for ld in lines_data:
    r = requests.post(f"{BASE}/api/v1/quote_versions/{vid}/lines", json=ld, headers=h)
    assert r.json()["code"] == 0
    print(f"  Added line: {ld['item_name']} -> total: {r.json()['data']['line_total']}")

# === 7. Get quote detail (verify totals) ===
r = requests.get(f"{BASE}/api/v1/quotes/{qid}", headers=h)
d = r.json()
assert d["code"] == 0
pp("7. Quote Detail", f"Lines: {len(d['data']['lines'])}, Total: {d['data']['current_version']['price_total']}")
print(f"  Margin Rate: {d['data']['current_version']['margin_rate']}")

# === 8. Create new version (lines should copy) ===
r = requests.post(f"{BASE}/api/v1/quotes/{qid}/new_version", headers=h)
d = r.json()
assert d["code"] == 0
new_vid = d["data"]["id"]
pp("8. New Version", f"Version V{d['data']['version_no']}, ID: {new_vid[:8]}...")

# Verify lines copied
r = requests.get(f"{BASE}/api/v1/quote_versions/{new_vid}", headers=h)
d = r.json()
assert d["code"] == 0
pp("8b. New Version Lines", f"Lines count: {len(d['data']['lines'])}")
assert len(d["data"]["lines"]) == 3, f"Expected 3 lines, got {len(d['data']['lines'])}"

# === 9. Create Contract ===
r = requests.post(f"{BASE}/api/v1/projects/{pid}/contracts", json={
    "title": "产线升级合同", "amount_total": 750000,
    "payment_terms_json": {"method": "分期", "schedule": ["30% 预付", "60% 到货", "10% 验收"]},
    "delivery_terms_json": {"location": "客户现场", "deadline": "2026-06-30"},
}, headers=h)
d = r.json()
assert d["code"] == 0
cid = d["data"]["contract"]["id"]
pp("9. Create Contract", f"Contract: {d['data']['contract']['contract_no']}, Amount: {d['data']['contract']['amount_total']}")

# === 10. Sign Contract ===
r = requests.post(f"{BASE}/api/v1/contracts/{cid}/sign", json={"signed_date": "2026-03-15"}, headers=h)
d = r.json()
pp("10. Sign Contract (raw)", d)
assert d["code"] == 0 and d["data"]["status"] == "signed", f"Sign failed: {d}"
pp("10. Sign Contract", f"Status: {d['data']['status']}, Signed: {d['data']['signed_date']}")

# === 11. Dashboard Stats ===
r = requests.get(f"{BASE}/api/v1/dashboard/stats", headers=h)
d = r.json()
assert d["code"] == 0
pp("11. Dashboard Stats", d["data"])

# === 12. List Projects ===
r = requests.get(f"{BASE}/api/v1/projects", params={"pageNo": 1, "pageSize": 10}, headers=h)
d = r.json()
assert d["code"] == 0 and d["data"]["total"] > 0
pp("12. List Projects", f"Total: {d['data']['total']}")

print("\n" + "="*60)
print("  ALL TESTS PASSED!")
print("="*60)
