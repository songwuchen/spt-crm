"""合同登记集成测试：最小正式提交 payload（对齐当前必填项）。"""

MIN_CONTRACT_LINE = {
    "is_fx": "否",
    "product_type": "复频筛",
    "name": "测试产品",
    "spec": "TEST-001",
    "unit": "台",
    "qty": 1,
    "price": 100,
}

MIN_REGISTRATION = {
    "project_name": "测试项目",
    "tax_included": "是",
    "is_export": "否",
    "need_install": "不需要安装",
    "info_complete": "是",
    "contract_form": "正式合同",
    "standard_delivery": "否",
    "is_rotary_sieve": "否",
    "paint_req": "企标",
    "workload": "设备",
    "payment_forms": ["电汇"],
    "payment_desc": "测试付款描述",
    "industry": "工业升级",
    "region": "华北",
    "application_field": "测试领域",
    "application_material": "测试物料",
    "has_intelligence": "否",
    "freight_payer": "我方",
}


def contract_registration_payload(**overrides) -> dict:
    """正式提交所需的登记表字段（不含合同明细子表）。"""
    import datetime

    today = datetime.date.today().isoformat()
    reg = dict(MIN_REGISTRATION)
    if overrides.get("registration_json"):
        reg.update(overrides.pop("registration_json"))
    base = {
        "card_date": today,
        "order_date": today,
        "delivery_date": today,
        "change_type": "new",
        "acquire_method": "协商一致",
        "amount_total": 1000,
        "peer_contract_no": "PEER-TEST-001",
        "registration_json": reg,
    }
    base.update(overrides)
    return base


def contract_submit_payload(**overrides) -> dict:
    """返回可过正式提交校验的最小合同字段（不含 customer_id / drawing_no 等）。"""
    base = contract_registration_payload(**overrides)
    if "key_clauses_json" not in base:
        base["key_clauses_json"] = [dict(MIN_CONTRACT_LINE)]
    return base
