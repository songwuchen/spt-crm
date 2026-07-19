"""原生字段策略：租户可为内置字段配置必填/条件显隐/只读，后端强制。

通过「发布线索实体系统模板」写入原生字段覆盖项，再打线索 API 验证行为。
"""
import pytest
from httpx import AsyncClient

from app.domains.lowcode.native_field_catalog import merge_native_overrides, get_native_fields


# ===== 目录合并（纯函数，无需 DB） =====

def test_override_can_make_optional_field_required():
    merged = merge_native_overrides("lead", [
        {"id": "industry", "native": True, "required": True},
    ])
    industry = next(f for f in merged if f["id"] == "industry")
    assert industry["required"] is True
    assert industry["type"] == "select", "type 必须来自目录，不受覆盖项影响"


def test_system_required_cannot_be_downgraded():
    """title 是 NOT NULL 列，租户不得把它改成非必填。"""
    merged = merge_native_overrides("lead", [
        {"id": "title", "native": True, "required": False},
    ])
    title = next(f for f in merged if f["id"] == "title")
    assert title["required"] is True
    assert title["system_required"] is True


def test_label_override_only_set_when_tenant_actually_renamed():
    """未改标签时不得透出 label_override，否则业务表单会被目录默认名覆盖既有文案。"""
    untouched = merge_native_overrides("lead", [])
    assert all("label_override" not in f for f in untouched)

    # 只改了必填、没动标签 → 仍不应有 label_override
    partial = merge_native_overrides("lead", [
        {"id": "biz_date", "native": True, "required": True},
    ])
    biz = next(f for f in partial if f["id"] == "biz_date")
    assert "label_override" not in biz
    assert biz["label"] == "业务日期"  # 目录默认名仍在，供设计器展示

    renamed = merge_native_overrides("lead", [
        {"id": "biz_date", "native": True, "label": "跟进日期"},
    ])
    assert next(f for f in renamed if f["id"] == "biz_date")["label_override"] == "跟进日期"


async def test_non_form_editable_field_can_be_masked_but_not_required(
    client: AsyncClient, auth_headers: dict,
):
    """form_editable=False 的字段（如合同签约日期，由签署流程写入）：
    仍可配隐藏/脱敏，但配了必填不得阻断保存 —— 用户根本没有填它的入口。
    """
    h = auth_headers
    cust_id = (await client.post("/api/v1/customers", json={"name": "签约日期测试客户"},
                                 headers=h)).json()["data"]["id"]
    proj_id = (await client.post("/api/v1/projects", json={
        "name": "签约日期测试商机", "customer_id": cust_id, "stage_code": "S1",
    }, headers=h)).json()["data"]["id"]

    tpl = (await client.get("/api/v1/lc/entity-templates/contract", headers=h)).json()["data"]

    async def publish(defs):
        await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/design", headers=h, json={
            "field_definitions": defs, "layout_definition": {}, "rule_definitions": []})
        await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/publish", headers=h)

    try:
        await publish([{"id": "signed_date", "native": True, "label": "签订日期",
                        "type": "date", "required": True}])
        r = (await client.post(f"/api/v1/projects/{proj_id}/contracts",
                               json={"amount_total": 100}, headers=h)).json()
        assert r["code"] == 0, f"表单上填不了的字段不该拦住保存: {r}"
        await client.delete(f"/api/v1/contracts/{r['data']['contract']['id']}", headers=h)
    finally:
        await publish([])


async def test_edit_only_field_does_not_block_creation(
    client: AsyncClient, auth_headers: dict,
):
    """available_on_create=False 的字段（如工单「解决方案」）配了必填也不得挡住新建 ——
    新建工单时还谈不上解决方案，界面上本就没有该输入项。
    """
    h = auth_headers
    tpl = (await client.get("/api/v1/lc/entity-templates/service_ticket", headers=h)).json()["data"]

    async def publish(defs):
        await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/design", headers=h, json={
            "field_definitions": defs, "layout_definition": {}, "rule_definitions": []})
        await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/publish", headers=h)

    try:
        await publish([{"id": "resolution", "native": True, "label": "解决方案",
                        "type": "textarea", "required": True}])
        r = (await client.post("/api/v1/service_tickets", headers=h, json={
            "type": "fault", "description": "设备无法启动",
        })).json()
        assert r["code"] == 0, f"新建工单不该被「解决方案」必填拦住: {r}"

        # 但编辑时该字段可见可填，必填照常生效
        tid = r["data"]["id"]
        upd = (await client.put(f"/api/v1/service_tickets/{tid}", headers=h,
                                json={"resolution": ""})).json()
        assert upd["code"] != 0 and "解决方案" in upd["message"]
        await client.delete(f"/api/v1/service_tickets/{tid}", headers=h)
    finally:
        await publish([])


def test_override_cannot_change_id_or_type():
    merged = merge_native_overrides("lead", [
        {"id": "industry", "native": True, "type": "detail_table", "label": "所属行业"},
    ])
    industry = next(f for f in merged if f["id"] == "industry")
    assert industry["type"] == "select", "改类型会写坏与业务列的映射，必须被忽略"
    assert industry["label"] == "所属行业", "label 属于可覆盖白名单"


def test_stale_override_for_removed_field_is_ignored():
    merged = merge_native_overrides("lead", [
        {"id": "__no_such_field__", "native": True, "required": True},
    ])
    assert all(f["id"] != "__no_such_field__" for f in merged)


def test_all_field_permission_keys_are_overridable():
    """字段级权限的三个键都必须在覆盖白名单里。

    回归：unmask_roles 曾漏加，导致租户在设计器里配了脱敏、合并时被静默丢弃 ——
    界面上看着配好了，实际一点也不生效。
    """
    from app.domains.lowcode.native_field_catalog import OVERRIDABLE_KEYS
    for key in ("visible_roles", "unmask_roles", "edit_roles"):
        assert key in OVERRIDABLE_KEYS, f"{key} 未列入 OVERRIDABLE_KEYS，租户配置会被丢弃"


def test_props_override_limited_to_hidden_and_readonly():
    merged = merge_native_overrides("lead", [
        {"id": "remark", "native": True, "props": {"readonly": True, "evil": "x"}},
    ])
    remark = next(f for f in merged if f["id"] == "remark")
    assert remark["props"]["readonly"] is True
    assert "evil" not in remark["props"]


def test_catalog_fields_all_have_a_form_control():
    """已接表单的实体（FORM_WIRED），其目录字段都必须有对应的 PolicyItem。

    否则会出现「后端按策略拦下、界面上却找不到该字段可填」的死角 —— 省市区就是因此被
    刻意排除的（它们由 RegionCascader 整体选择，只有隐藏桩）。
    未接表单的实体只服务读取路径，不受此约束。
    """
    import re
    from pathlib import Path
    from app.domains.lowcode.native_field_catalog import FORM_WIRED

    # 一个实体可能有多处表单，且新建与编辑能填的字段并不相同：
    # (相对路径, 该表单覆盖的场景)  场景 ∈ {"create", "edit", "both"}
    forms = {
        "lead": [("frontend/src/pages/lead/LeadForm.tsx", "both")],
        "customer": [("frontend/src/pages/customer/CustomerForm.tsx", "both")],
        "contact": [
            ("frontend/src/pages/customer/CustomerDetail.tsx", "both"),
            ("frontend/src/pages/customer/ContactList.tsx", "create"),
        ],
        "project": [("frontend/src/pages/opportunity/OpportunityForm.tsx", "both")],
        "contract": [("frontend/src/pages/contract/ContractList.tsx", "create")],
        "order": [("frontend/src/pages/order/OrderList.tsx", "both")],
        "service_ticket": [
            ("frontend/src/pages/service/ServiceTicketList.tsx", "create"),
            ("frontend/src/pages/service/ServiceTicketDetail.tsx", "edit"),
        ],
        "payment": [("frontend/src/pages/payment/PaymentPage.tsx", "create")],
    }
    root = Path(__file__).resolve().parents[2]
    for entity in FORM_WIRED:
        assert entity in forms, f"{entity} 已声明接入表单，但测试不知道它的表单文件在哪"
        for rel, scope in forms[entity]:
            src = (root / rel).read_text(encoding="utf-8")
            rendered = set(re.findall(r'<PolicyItem\s+name="([^"]+)"', src))
            missing = []
            for fd in get_native_fields(entity):
                if not fd.get("form_editable", True):
                    continue  # 由系统/专用流程写入，表单上本就没有输入项
                if scope == "create" and not fd.get("available_on_create", True):
                    continue  # 只在记录建立后才出现的字段（如工单解决方案）
                if fd["id"] not in rendered:
                    missing.append(fd["id"])
            assert not missing, f"{entity} @ {rel}({scope}): 目录里有但表单没有对应 PolicyItem: {missing}"


# 目录里的实体 -> (模型模块, 类名)，用于校验字段 id 都是真实列
_ENTITY_MODELS = {
    "lead": ("app.domains.lead.models", "Lead"),
    "customer": ("app.domains.customer.models", "Customer"),
    "contact": ("app.domains.customer.models", "Contact"),
    "project": ("app.domains.project.models", "OpportunityProject"),
    "contract": ("app.domains.contract.models", "Contract"),
    "quote": ("app.domains.quote.models", "Quote"),
    "order": ("app.domains.order.models", "Order"),
    "service_ticket": ("app.domains.service_ticket.models", "ServiceTicket"),
    "payment": ("app.domains.payment.models", "PaymentRecord"),
}


@pytest.mark.parametrize("entity", sorted(_ENTITY_MODELS))
def test_catalog_ids_are_real_columns(entity):
    """目录里的 id 必须是该实体表上真实存在的列。

    回归：被删掉的旧 field_rules UI 里 18 个字段有 12 个是不存在的列（customer.phone、
    contract.amount、quote.margin_rate 等），配了规则也永远匹配不到 —— 新目录不能重蹈覆辙。
    """
    import importlib
    from app.domains.lowcode.native_field_catalog import CATALOG

    mod, cls = _ENTITY_MODELS[entity]
    model = getattr(importlib.import_module(mod), cls)
    columns = set(model.__table__.columns.keys())
    for fd in get_native_fields(entity):
        assert fd["id"] in columns, f"{entity}.{fd['id']} 不是 {model.__tablename__} 表的列"
    assert entity in CATALOG, f"{entity} 应在 CATALOG 中"


def test_every_catalog_entity_is_covered_by_column_check():
    """新增实体目录时必须同步补 _ENTITY_MODELS，否则字段名校验会静默跳过它。"""
    from app.domains.lowcode.native_field_catalog import CATALOG
    missing = set(CATALOG) - set(_ENTITY_MODELS)
    assert not missing, f"这些实体有目录但没纳入列名校验: {missing}"


# ===== 端到端：经 API 配置后生效 =====

async def _publish_lead_native_override(client: AsyncClient, h: dict, overrides: list[dict],
                                        rules: list[dict] | None = None):
    tpl = (await client.get("/api/v1/lc/entity-templates/lead", headers=h)).json()["data"]
    body = {"field_definitions": overrides, "layout_definition": {}, "rule_definitions": rules or []}
    r = await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/design", headers=h, json=body)
    assert r.json()["code"] == 0, r.text
    r = await client.post(f"/api/v1/lc/form-templates/{tpl['id']}/publish", headers=h)
    assert r.json()["code"] == 0, r.text
    return tpl["id"]


@pytest.fixture
async def reset_lead_template(client: AsyncClient, auth_headers: dict):
    """前后各清空发布一次线索实体模板。

    这些用例改的是种子租户里真实的实体模板，测试库又是共用的。只在结束时清理不够：
    上一轮若被中断（Ctrl-C / 进程被杀），残留的必填或脱敏覆盖会让后续 test_lead.py
    莫名其妙地失败，且跨进程持续存在。故进入时也先清一次。
    """
    await _publish_lead_native_override(client, auth_headers, [])
    yield
    await _publish_lead_native_override(client, auth_headers, [])


async def test_tenant_configured_required_is_enforced(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    h = auth_headers
    await _publish_lead_native_override(client, h, [
        {"id": "industry", "native": True, "required": True, "label": "行业", "type": "select"},
    ])

    # 缺行业 → 被后端拦下
    resp = (await client.post("/api/v1/leads", headers=h, json={
        "title": "缺行业线索", "company_name": "某公司",
    })).json()
    assert resp["code"] != 0
    assert "行业" in resp["message"]

    # 补上行业 → 通过
    ok = (await client.post("/api/v1/leads", headers=h, json={
        "title": "有行业线索", "company_name": "某公司", "industry": "mining",
    })).json()
    assert ok["code"] == 0
    await client.delete(f"/api/v1/leads/{ok['data']['id']}", headers=h)


async def test_company_name_default_required_but_tenant_can_relax(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """company_name 列可空，改造前表单硬编码必填；改造后默认仍必填，但租户可关掉。"""
    h = auth_headers

    # 出厂默认：不填公司名被拦（保持改造前行为）
    resp = (await client.post("/api/v1/leads", headers=h, json={"title": "无公司名线索"})).json()
    assert resp["code"] != 0 and "公司名称" in resp["message"]

    # 租户把它改成非必填 → 放行
    await _publish_lead_native_override(client, h, [
        {"id": "company_name", "native": True, "required": False, "label": "公司名称", "type": "text"},
    ])
    ok = (await client.post("/api/v1/leads", headers=h, json={"title": "无公司名线索"})).json()
    assert ok["code"] == 0, f"租户已关掉必填，不应再被拦: {ok}"
    await client.delete(f"/api/v1/leads/{ok['data']['id']}", headers=h)


async def test_conditional_visibility_suppresses_required(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """国家名设为必填、但仅在国别=国外时显示：国内提交不应被必填拦住（防死锁）。"""
    h = auth_headers
    await _publish_lead_native_override(client, h, [
        {"id": "country_name", "native": True, "required": True, "label": "国家", "type": "text"},
    ], rules=[{
        "id": "r1", "type": "visibility", "target_field_id": "country_name",
        "condition": {"field": "country_type", "operator": "eq", "value": "overseas"},
        "action": {"visible": True},
    }])

    domestic = (await client.post("/api/v1/leads", headers=h, json={
        "title": "国内线索", "company_name": "某公司", "country_type": "domestic",
    })).json()
    assert domestic["code"] == 0, f"字段被规则隐藏时不得报必填: {domestic}"
    await client.delete(f"/api/v1/leads/{domestic['data']['id']}", headers=h)

    overseas = (await client.post("/api/v1/leads", headers=h, json={
        "title": "国外线索", "company_name": "某公司", "country_type": "overseas",
    })).json()
    assert overseas["code"] != 0 and "国家" in overseas["message"]


async def test_partial_update_skips_untouched_required_fields(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """批量改派这类局部更新，不应因历史数据缺少「后来才设为必填」的字段而失败。"""
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "历史线索", "company_name": "老公司",
    })).json()["data"]["id"]

    await _publish_lead_native_override(client, h, [
        {"id": "industry", "native": True, "required": True, "label": "行业", "type": "select"},
    ])

    # 只改状态：不带 industry → 放行
    r = (await client.put(f"/api/v1/leads/{lid}", headers=h, json={"status": "following"})).json()
    assert r["code"] == 0, f"局部更新不应被未提交的必填字段拦住: {r}"

    # 表单整体提交且把 industry 显式留空 → 拦下
    r = (await client.put(f"/api/v1/leads/{lid}", headers=h, json={
        "title": "历史线索", "company_name": "老公司", "industry": None,
    })).json()
    assert r["code"] != 0 and "行业" in r["message"]

    await client.delete(f"/api/v1/leads/{lid}", headers=h)


async def test_native_field_masking_on_read_paths(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """角色键控脱敏：无「可见明文角色」的用户在列表与详情上都只拿到 ***。

    这是被删掉的 field_rules Tab 曾经承诺、却从未真正实现的能力（那套后端零执行点）。
    """
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "脱敏线索", "company_name": "某公司", "budget_range": "100-500万",
    })).json()["data"]["id"]

    # 明文可见角色设为一个当前用户不具备的角色 → 该用户应只看到 ***
    await _publish_lead_native_override(client, h, [
        {"id": "budget_range", "native": True, "label": "预算范围", "type": "select",
         "unmask_roles": ["__finance_only__"]},
    ])

    detail = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert detail["budget_range"] == "***", f"详情未脱敏: {detail['budget_range']!r}"

    listed = (await client.get("/api/v1/leads", headers=h,
                               params={"keyword": "脱敏线索"})).json()["data"]["items"]
    row = next(i for i in listed if i["id"] == lid)
    assert row["budget_range"] == "***", f"列表未脱敏: {row['budget_range']!r}"

    # 撤掉限制 → 恢复明文，确认脱敏未把真实值写坏
    await _publish_lead_native_override(client, h, [])
    after = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert after["budget_range"] == "100-500万", "脱敏只应影响出参，不得改动库里的真实值"

    await client.delete(f"/api/v1/leads/{lid}", headers=h)


async def test_masked_and_required_is_not_a_deadlock(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """脱敏 + 必填不得让记录永远存不下去 —— 看不到明文的人无法填写该字段。"""
    h = auth_headers
    await _publish_lead_native_override(client, h, [
        {"id": "budget_range", "native": True, "label": "预算范围", "type": "select",
         "required": True, "unmask_roles": ["__finance_only__"]},
    ])
    r = (await client.post("/api/v1/leads", headers=h, json={
        "title": "脱敏必填线索", "company_name": "某公司",
    })).json()
    assert r["code"] == 0, f"脱敏字段不应报必填(用户无从填写): {r}"
    await client.delete(f"/api/v1/leads/{r['data']['id']}", headers=h)


async def test_country_name_required_does_not_block_domestic_lead(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """「国家」只在国别=国外时才在表单上出现，内置规则须让国内线索免于该必填。

    否则租户一旦给「国家」勾必填，国内线索会被后端拦下、界面上却找不到这个字段可填。
    """
    h = auth_headers
    await _publish_lead_native_override(client, h, [
        {"id": "country_name", "native": True, "label": "国家", "type": "text", "required": True},
    ])

    domestic = (await client.post("/api/v1/leads", headers=h, json={
        "title": "国内线索", "company_name": "某公司", "country_type": "domestic",
    })).json()
    assert domestic["code"] == 0, f"国内线索不应被「国家」必填拦住: {domestic}"
    await client.delete(f"/api/v1/leads/{domestic['data']['id']}", headers=h)

    # 国外线索该字段确实出现在表单上，必填照常生效
    overseas = (await client.post("/api/v1/leads", headers=h, json={
        "title": "国外线索", "company_name": "某公司", "country_type": "overseas",
    })).json()
    assert overseas["code"] != 0 and "国家" in overseas["message"]


async def test_masking_covers_derived_display_fields(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """脱敏 owner_id 必须连带 owner_name —— 列表页渲染的正是后者。"""
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "派生字段脱敏线索", "company_name": "某公司",
    })).json()["data"]["id"]

    before = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert before["owner_name"], "前置条件：该线索应有负责人姓名"

    await _publish_lead_native_override(client, h, [
        {"id": "owner_id", "native": True, "label": "负责人", "type": "person",
         "unmask_roles": ["__manager_only__"]},
    ])
    after = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert after["owner_id"] == "***"
    assert after["owner_name"] == "***", "只裁 owner_id 而漏了 owner_name，脱敏等于没配"

    await client.delete(f"/api/v1/leads/{lid}", headers=h)


async def test_export_respects_field_policy(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """导出必须与页面同口径脱敏，否则「看不到但导得出」= 绕过字段权限的后门。"""
    from openpyxl import load_workbook
    import io as _io

    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "导出脱敏线索", "company_name": "某公司", "budget_range": "100-500万",
    })).json()["data"]["id"]

    def budget_cells(content: bytes):
        wb = load_workbook(_io.BytesIO(content))
        ws = wb.active
        header = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        idx = header.index("预算范围")
        return [row[idx].value for row in ws.iter_rows(min_row=2)]

    # 未配置时导出明文
    plain = (await client.get("/api/v1/leads/export/excel", headers=h,
                              params={"keyword": "导出脱敏线索"})).content
    assert "100-500万" in budget_cells(plain)

    # 配置为仅特定角色可见明文 → 导出应变成 ***
    await _publish_lead_native_override(client, h, [
        {"id": "budget_range", "native": True, "label": "预算范围", "type": "select",
         "unmask_roles": ["__finance_only__"]},
    ])
    masked = (await client.get("/api/v1/leads/export/excel", headers=h,
                               params={"keyword": "导出脱敏线索"})).content
    cells = budget_cells(masked)
    assert "100-500万" not in cells, "导出泄露了页面上已脱敏的字段"
    assert "***" in cells

    await client.delete(f"/api/v1/leads/{lid}", headers=h)


async def test_masked_native_field_write_is_discarded(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    """被脱敏的字段一律不可编辑 —— 否则用户会把 "***" 当成真值提交回去。"""
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "脱敏只读线索", "company_name": "某公司", "budget_range": "100-500万",
    })).json()["data"]["id"]

    await _publish_lead_native_override(client, h, [
        {"id": "budget_range", "native": True, "label": "预算范围", "type": "select",
         "unmask_roles": ["__finance_only__"]},
    ])
    await client.put(f"/api/v1/leads/{lid}", headers=h, json={"budget_range": "***"})

    await _publish_lead_native_override(client, h, [])
    after = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert after["budget_range"] == "100-500万", "脱敏字段的写入必须被丢弃，不能用 *** 覆盖真值"

    await client.delete(f"/api/v1/leads/{lid}", headers=h)


async def test_readonly_native_field_ignores_user_write(
    client: AsyncClient, auth_headers: dict, reset_lead_template,
):
    h = auth_headers
    lid = (await client.post("/api/v1/leads", headers=h, json={
        "title": "只读字段线索", "company_name": "原始公司", "remark": "原始备注",
    })).json()["data"]["id"]

    await _publish_lead_native_override(client, h, [
        {"id": "remark", "native": True, "label": "备注", "type": "textarea",
         "props": {"readonly": True}},
    ])

    await client.put(f"/api/v1/leads/{lid}", headers=h, json={"remark": "偷改的备注"})
    after = (await client.get(f"/api/v1/leads/{lid}", headers=h)).json()["data"]
    assert after["remark"] == "原始备注", "只读原生字段的写入必须被后端丢弃"

    await client.delete(f"/api/v1/leads/{lid}", headers=h)
