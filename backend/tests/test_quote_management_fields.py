"""报价管理：成本价仅内勤/财务/销售经理/管理员可见。"""
from app.domains.lowcode.field_permission import filter_read
from app.domains.lowcode.quote_management_fields import (
    QUOTE_COST_VISIBLE_ROLES,
    apply_quote_management_fields,
    prepare_quote_field_defs,
)

_SAMPLE_DEFS = [
    {"id": "customer_name", "type": "text", "label": "客户名称"},
    {"id": "cost_price", "type": "number", "label": "成本价", "fill_stage": "approver"},
    {
        "id": "cost_attachments",
        "type": "file",
        "label": "成本价附件",
        "fill_stage": "approver",
    },
]

_SAMPLE_DATA = {
    "customer_name": "测试客户",
    "cost_price": 12345.6,
    "cost_attachments": [{"id": "att-1", "name": "成本.xlsx"}],
}


def test_apply_quote_cost_field_acl_roles():
    defs = prepare_quote_field_defs(_SAMPLE_DEFS)
    by_id = {f["id"]: f for f in defs}
    for fid in ("cost_price", "cost_attachments"):
        assert by_id[fid]["visible_roles"] == QUOTE_COST_VISIBLE_ROLES
        assert by_id[fid]["unmask_roles"] == QUOTE_COST_VISIBLE_ROLES
    assert by_id["cost_attachments"]["download_roles"] == QUOTE_COST_VISIBLE_ROLES


def test_salesperson_cannot_see_cost_price_even_as_creator():
    defs = prepare_quote_field_defs(_SAMPLE_DEFS)
    out_defs, data = filter_read(
        defs, _SAMPLE_DATA, ["salesperson"], is_creator=True,
    )
    ids = {f["id"] for f in out_defs}
    assert "cost_price" not in ids
    assert "cost_attachments" not in ids
    assert "cost_price" not in data
    assert "cost_attachments" not in data
    assert data["customer_name"] == "测试客户"


def test_finance_and_sales_manager_can_see_cost():
    defs = prepare_quote_field_defs(_SAMPLE_DEFS)
    for role in ("finance", "sales_manager", "lead_intel", "admin", "mkt_support"):
        _, data = filter_read(defs, _SAMPLE_DATA, [role])
        assert data["cost_price"] == 12345.6
        assert data["cost_attachments"] == _SAMPLE_DATA["cost_attachments"]


def test_apply_quote_management_inserts_related_project():
    defs = [{"id": "customer_name", "type": "text", "label": "客户名称"}]
    apply_quote_management_fields(defs)
    assert defs[0]["id"] == "related_project"
    assert defs[1]["id"] == "customer_name"
