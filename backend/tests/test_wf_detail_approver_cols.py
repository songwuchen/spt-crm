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
    perms = [{"field": "field_7", "access": "editable"}]
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
