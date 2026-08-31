"""表单列表筛选：部门/人员按名称解析；合同按合同号/图纸编号解析。"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import generate_uuid
from app.domains.contract.models import Contract
from app.domains.lowcode.models import FormInstance, FormTemplate, FormTemplateVersion
from app.domains.lowcode.service import (
    _UUID_RE,
    _flatten_filter_values,
    _form_data_filter_clause,
    _lookup_ref_ids_by_name,
    _normalize_instance_filters,
    _person_name_chars_all_present,
    list_instances,
)

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
async def db():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_uuid_detect():
    assert _UUID_RE.match("d017a32d-91e1-44fb-bda5-96ae3994a897")
    assert not _UUID_RE.match("砂石")


def test_flatten_filter_values():
    assert _flatten_filter_values("砂石") == ["砂石"]
    assert _flatten_filter_values(["a", " b ", ""]) == ["a", "b"]
    assert _flatten_filter_values(None) == []


def test_normalize_initiator_filter_rule():
    match, rules = _normalize_instance_filters({
        "match": "all",
        "rules": [{"field": "__sys_initiator", "op": "contains", "value": "岳毅"}],
    })
    assert match == "all"
    assert rules == [{"field": "__sys_initiator", "op": "contains", "value": "岳毅"}]


def test_normalize_contains_rule():
    match, rules = _normalize_instance_filters({
        "match": "all",
        "rules": [{"field": "department", "op": "contains", "value": "砂石"}],
    })
    assert match == "all"
    assert rules == [{"field": "department", "op": "contains", "value": "砂石"}]


def test_plain_contains_still_works_for_text():
    clause = _form_data_filter_clause({
        "field": "dept_code", "op": "contains", "value": "03",
    })
    assert clause is not None


@pytest.mark.asyncio
async def test_contains_does_not_match_unrelated_form_fields(db):
    """「包含」只匹配目标 field，不因 form_data 其它键含相同片段而误命中。"""
    token = generate_uuid()[:8]
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        name=f"ut-contains-fp-{token}", code=f"ut_cf_fp_{token}",
        status="published", current_version=1,
    )
    ver = FormTemplateVersion(
        id=generate_uuid(), tenant_id=DEMO_TENANT, template_id=tpl.id,
        version_number=1, status="published",
        field_definitions=[
            {"id": "no_drawing_no", "type": "text", "label": "图纸编号"},
        ],
        layout_definition={}, rule_definitions=[],
    )
    miss_inst = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=tpl.id, template_version_id=ver.id,
        title="miss", status="running", initiator_id="ut-admin",
        form_data={
            "no_drawing_no": "WMGF202608001",
            "remark_prod_card": "历史单号 1.2.3-2026081501456 备注",
        },
        field_definitions=[],
    )
    hit_inst = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=tpl.id, template_version_id=ver.id,
        title="hit", status="running", initiator_id="ut-admin",
        form_data={"no_drawing_no": "1.2.3-2026081501458"},
        field_definitions=[],
    )
    db.add_all([tpl, ver, miss_inst, hit_inst])
    await db.commit()
    try:
        filt = {"match": "all", "rules": [
            {"field": "no_drawing_no", "op": "contains", "value": "202608150"},
        ]}
        rows, total = await list_instances(db, DEMO_TENANT, tpl.id, 1, 20, filters=filt)
        ids = {r.id for r in rows}
        assert hit_inst.id in ids
        assert miss_inst.id not in ids
        assert total == 1
    finally:
        await db.delete(hit_inst)
        await db.delete(miss_inst)
        await db.delete(ver)
        await db.delete(tpl)
        await db.commit()


@pytest.mark.asyncio
async def test_radio_eq_does_not_match_other_fields_with_same_value(db):
    """radio eq「否」不应因其它字段值为「否」而误命中（如 is_after_sales=是 但 is_reship=否）。"""
    token = generate_uuid()[:8]
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        name=f"ut-radio-eq-{token}", code=f"ut_re_{token}",
        status="published", current_version=1,
    )
    ver = FormTemplateVersion(
        id=generate_uuid(), tenant_id=DEMO_TENANT, template_id=tpl.id,
        version_number=1, status="published",
        field_definitions=[
            {"id": "is_after_sales", "type": "radio", "label": "是否售后",
             "options": [{"label": "是", "value": "是"}, {"label": "否", "value": "否"}]},
        ],
        layout_definition={}, rule_definitions=[],
    )
    yes_inst = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=tpl.id, template_version_id=ver.id,
        title="yes", status="running", initiator_id="ut-admin",
        form_data={"is_after_sales": "是", "is_reship": "否", "need_weigh": "否"},
        field_definitions=[],
    )
    no_inst = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=tpl.id, template_version_id=ver.id,
        title="no", status="running", initiator_id="ut-admin",
        form_data={"is_after_sales": "否", "is_reship": "是"},
        field_definitions=[],
    )
    db.add_all([tpl, ver, yes_inst, no_inst])
    await db.commit()
    try:
        filt = {"match": "all", "rules": [{"field": "is_after_sales", "op": "eq", "value": "否"}]}
        rows, total = await list_instances(db, DEMO_TENANT, tpl.id, 1, 20, filters=filt)
        ids = {r.id for r in rows}
        assert no_inst.id in ids
        assert yes_inst.id not in ids
        assert total == 1
    finally:
        await db.delete(yes_inst)
        await db.delete(no_inst)
        await db.delete(ver)
        await db.delete(tpl)
        await db.commit()


def test_person_name_chars_all_present():
    assert _person_name_chars_all_present("尚高华", "高尚")
    assert _person_name_chars_all_present("王高尚", "高尚")
    assert _person_name_chars_all_present("尚高华", "高华")
    assert not _person_name_chars_all_present("张三", "高尚")
    assert not _person_name_chars_all_present("尚高华", "高")  # 单字仍走 ILIKE


@pytest.mark.asyncio
async def test_contract_filter_matches_drawing_no(db):
    """合同号字段存 UUID，筛选「包含图纸编号片段」应命中。"""
    token = generate_uuid()[:8]
    drawing_no = f"WMGFUT{token}"
    contract = Contract(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        contract_no=f"YJ-UT-{token}", drawing_no=drawing_no, status="draft",
    )
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        name=f"ut-contract-filter-{token}", code=f"ut_cf_{token}",
        status="published", current_version=1,
    )
    ver = FormTemplateVersion(
        id=generate_uuid(), tenant_id=DEMO_TENANT, template_id=tpl.id,
        version_number=1, status="published",
        field_definitions=[{"id": "contract_no", "type": "contract", "label": "合同号"}],
        layout_definition={}, rule_definitions=[],
    )
    inst = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=tpl.id, template_version_id=ver.id,
        title="ut", status="running", initiator_id="ut-admin",
        form_data={"contract_no": contract.id}, field_definitions=[],
    )
    db.add_all([contract, tpl, ver, inst])
    await db.commit()
    try:
        ids = await _lookup_ref_ids_by_name(
            db, DEMO_TENANT, kind="contract", value=token, exact=False,
        )
        assert contract.id in ids

        rows, total = await list_instances(
            db, DEMO_TENANT, tpl.id, 1, 20,
            filters={"match": "all", "rules": [
                {"field": "contract_no", "op": "contains", "value": token},
            ]},
        )
        assert total >= 1
        assert any(r.id == inst.id for r in rows)

        _miss, miss_n = await list_instances(
            db, DEMO_TENANT, tpl.id, 1, 20,
            filters={"match": "all", "rules": [
                {"field": "contract_no", "op": "contains", "value": "NO_SUCH_DRAWING_XYZ"},
            ]},
        )
        assert miss_n == 0
    finally:
        # 测完硬删，避免污染本地「自定义表单」列表
        await db.delete(inst)
        await db.delete(ver)
        await db.delete(tpl)
        await db.delete(contract)
        await db.commit()


@pytest.mark.asyncio
async def test_contract_filter_matches_detail_table_column(db):
    """明细子表内合同号（如售出产品更换 field_12.contract_no）也可按图纸号筛选。"""
    token = generate_uuid()[:8]
    drawing_no = f"WMGFDT{token}"
    contract = Contract(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        contract_no=f"YJ-DT-{token}", drawing_no=drawing_no, status="draft",
    )
    tpl = FormTemplate(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        name=f"ut-detail-contract-filter-{token}", code=f"ut_dcf_{token}",
        status="published", current_version=1,
    )
    ver = FormTemplateVersion(
        id=generate_uuid(), tenant_id=DEMO_TENANT, template_id=tpl.id,
        version_number=1, status="published",
        field_definitions=[{
            "id": "field_12", "type": "detail_table", "label": "换货（含补发）",
            "detail_table_columns": [
                {"id": "contract_no", "type": "contract", "label": "合同号"},
                {"id": "field_13", "type": "text", "label": "设备名称"},
            ],
        }],
        layout_definition={}, rule_definitions=[],
    )
    inst = FormInstance(
        id=generate_uuid(), tenant_id=DEMO_TENANT,
        template_id=tpl.id, template_version_id=ver.id,
        title="ut-detail", status="running", initiator_id="ut-admin",
        form_data={"field_12": [{"contract_no": contract.id, "field_13": "泵"}]},
        field_definitions=[],
    )
    db.add_all([contract, tpl, ver, inst])
    await db.commit()
    try:
        rows, total = await list_instances(
            db, DEMO_TENANT, tpl.id, 1, 20,
            filters={"match": "all", "rules": [
                {"field": "contract_no", "op": "contains", "value": token},
            ]},
        )
        assert total >= 1
        assert any(r.id == inst.id for r in rows)
    finally:
        await db.delete(inst)
        await db.delete(ver)
        await db.delete(tpl)
        await db.delete(contract)
        await db.commit()
