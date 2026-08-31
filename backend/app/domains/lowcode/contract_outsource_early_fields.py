"""合同外购件提前安排：字段阶段修正。

设备明细（含设计员）在简道云由设计员节点填写，发起时不应展示。
"""


def apply_contract_outsource_early_fields(defs: list) -> None:
    for fd in defs:
        if not isinstance(fd, dict) or fd.get("id") != "equipment_details":
            continue
        fd["available_on_create"] = False
        fd["fill_stage"] = "approver"
        fd["required"] = True
        for col in fd.get("detail_table_columns") or []:
            if not isinstance(col, dict):
                continue
            col["available_on_create"] = False
            col["fill_stage"] = "approver"
            if col.get("id") == "designer":
                col["required"] = True
        return
