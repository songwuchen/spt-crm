# -*- coding: utf-8 -*-
import pytest
from sqlalchemy import delete

from app.database import generate_uuid
from app.domains.lowcode.models import FormInstance, FormTemplate, FormTemplateVersion
from app.domains.lowcode.payment_registration_fields import apply_payment_registration_fields
from app.domains.lowcode.formula_engine import compute_formula_fields


def test_apply_payment_registration_fields():
    defs = [
        {"id": "payment_no", "type": "text", "label": "收款号"},
        {"id": "payment_date", "type": "datetime", "label": "来款日期", "required": True},
        {"id": "customer_name", "type": "text", "label": "单位名称"},
        {"id": "payment_total", "type": "number", "label": "来款合计", "available_on_create": True},
        {"id": "sales_person", "type": "person", "label": "业务人员", "available_on_create": True},
        {
            "id": "payment_details",
            "type": "detail_table",
            "label": "来款明细",
            "detail_table_columns": [
                {"id": "amount", "type": "number", "label": "金额"},
                {"id": "due_date", "type": "datetime", "label": "到期日"},
            ],
        },
        {"id": "payment_allocation", "type": "detail_table", "label": "款项分配"},
        {"id": "alloc_total", "type": "number", "label": "分配金额合计"},
        {"id": "remark_2", "type": "textarea", "label": "备注"},
    ]
    apply_payment_registration_fields(defs)
    assert defs[0]["type"] == "auto_number"
    assert defs[0]["form_editable"] is False
    assert defs[0]["props"]["serial_rules"][0]["value"] == "SKDJ-"
    assert defs[1]["type"] == "date"
    assert defs[1]["props"]["date_only"] is True
    assert defs[1]["props"]["show_time"] is False
    assert defs[2]["type"] == "customer"
    assert defs[3]["type"] == "formula"
    assert defs[3]["props"]["formula"] == "SUM($payment_details.amount#)"
    due_col = next(c for c in defs[5]["detail_table_columns"] if c["id"] == "due_date")
    assert due_col["type"] == "date"
    assert due_col["props"]["date_only"] is True
    assert due_col["props"]["show_time"] is False
    assert defs[4]["available_on_create"] is False
    assert defs[4]["fill_stage"] == "approver"
    assert defs[6]["available_on_create"] is False
    assert defs[7]["type"] == "formula"
    assert defs[7]["available_on_create"] is False
    assert defs[8]["available_on_create"] is False


def test_payment_total_formula_sums_details():
    defs = [
        {
            "id": "payment_details",
            "type": "detail_table",
            "detail_table_columns": [{"id": "amount", "type": "number"}],
        },
        {
            "id": "payment_total",
            "type": "formula",
            "props": {"formula": "SUM($payment_details.amount#)"},
        },
    ]
    data = compute_formula_fields(
        {"payment_details": [{"amount": 10}, {"amount": 25.5}]},
        defs,
        "",
    )
    assert float(data["payment_total"]) == 35.5


@pytest.mark.asyncio
async def test_form_instance_summary_sums_payment_total(db):
    from sqlalchemy import select

    from app.domains.lowcode.service import form_instance_summary

    tenant = "00000000-0000-0000-0000-000000000001"
    tpl_id = generate_uuid()
    ver_id = generate_uuid()
    db.add(FormTemplate(
        id=tpl_id, tenant_id=tenant, code=f"payment_registration_ut_{tpl_id[:8]}", name="收款登记UT",
        status="published", is_deleted=False,
    ))
    db.add(FormTemplateVersion(
        id=ver_id, tenant_id=tenant, template_id=tpl_id, version_number=1,
        status="published", field_definitions=[], rule_definitions=[],
    ))
    await db.flush()
    db.add_all([
        FormInstance(
            id=generate_uuid(), tenant_id=tenant, template_id=tpl_id,
            template_version_id=ver_id, title="A", status="completed",
            initiator_id="u1", form_data={"payment_total": "100.5", "payment_date": "2026-03-01"},
            field_definitions=[], is_deleted=False,
        ),
        FormInstance(
            id=generate_uuid(), tenant_id=tenant, template_id=tpl_id,
            template_version_id=ver_id, title="B", status="completed",
            initiator_id="u1", form_data={"payment_total": "200", "payment_date": "2026-04-01"},
            field_definitions=[], is_deleted=False,
        ),
        FormInstance(
            id=generate_uuid(), tenant_id=tenant, template_id=tpl_id,
            template_version_id=ver_id, title="C", status="completed",
            initiator_id="u1", form_data={"payment_total": "999", "payment_date": "2025-12-01"},
            field_definitions=[], is_deleted=False,
        ),
    ])
    await db.commit()

    out = await form_instance_summary(
        db, tenant, tpl_id, sum_field="payment_total", owner_ids=None,
        filters={
            "match": "all",
            "rules": [{
                "field": "payment_date", "op": "between",
                "value": ["2026-01-01", "2026-12-31"],
            }],
        },
        user={"sub": "u1"},
    )
    assert out["count"] == 2
    assert abs(out["sum"] - 300.5) < 0.01

    await db.execute(delete(FormInstance).where(FormInstance.template_id == tpl_id))
    await db.execute(delete(FormTemplateVersion).where(FormTemplateVersion.template_id == tpl_id))
    await db.execute(delete(FormTemplate).where(FormTemplate.id == tpl_id))
    await db.commit()
