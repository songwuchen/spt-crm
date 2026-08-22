# -*- coding: utf-8 -*-
"""明细表审批列（fill_stage=approver）校验。"""
from __future__ import annotations

import pytest

from app.common.exceptions import BusinessException
from app.domains.lowcode.wf_field_writeback import validate_field_updates


def test_validate_field_updates_requires_approver_detail_column():
    form_fields = [{
        "id": "field_7",
        "type": "detail_table",
        "label": "售出产品退回",
        "detail_table_columns": [
            {"id": "contract_no", "label": "合同号", "type": "text", "required": True},
            {
                "id": "field_14",
                "label": "仓库判定*",
                "type": "radio",
                "required": True,
                "fill_stage": "approver",
                "available_on_create": False,
            },
        ],
    }]
    # editable：可改明细，不强制审批列（物流中心等）
    editable_ok = validate_field_updates(
        [{"field": "field_7", "access": "editable"}],
        {"field_7": [{"contract_no": "HT001"}]},
        action="approve",
        form_fields=form_fields,
    )
    assert editable_ok["field_7"][0]["contract_no"] == "HT001"

    perms = [{"field": "field_7", "access": "required"}]
    with pytest.raises(BusinessException) as exc:
        validate_field_updates(
            perms,
            {"field_7": [{"contract_no": "HT001"}]},
            action="approve",
            form_fields=form_fields,
        )
    assert "仓库判定" in (exc.value.message or "")
    ok = validate_field_updates(
        perms,
        {"field_7": [{"contract_no": "HT001", "field_14": "生产维修"}]},
        action="approve",
        form_fields=form_fields,
    )
    assert ok["field_7"][0]["field_14"] == "生产维修"


def test_logistics_node_only_requires_logistics_status():
    """物流中心：有退回明细但无仓库判定时，仅校验物流情况即可通过。"""
    form_fields = [
        {
            "id": "field_7",
            "type": "detail_table",
            "label": "售出产品退回",
            "detail_table_columns": [
                {"id": "contract_no", "label": "合同号", "type": "text"},
                {
                    "id": "field_14",
                    "label": "仓库判定*",
                    "type": "radio",
                    "required": True,
                    "fill_stage": "approver",
                },
            ],
        },
        {"id": "field_25", "type": "radio", "label": "物流情况"},
    ]
    form_data = {"field_7": [{"contract_no": "ZJB25055"}]}
    # 对齐修正后的 n17：仅 field_25 required
    ok = validate_field_updates(
        [{"field": "field_25", "access": "required"}],
        {"field_25": "下转提交"},
        action="approve",
        form_fields=form_fields,
        form_data=form_data,
    )
    assert ok["field_25"] == "下转提交"
