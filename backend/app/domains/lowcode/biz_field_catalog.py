"""业务类型审批流的「业务字段目录」。

绑定业务类型(而非表单)的审批流没有表单字段，可视化设计器用本目录填充条件分支/
字段选择；引擎侧由 approval._build_policy_context 载入这些字段的实际值进条件上下文，
两者字段名保持一致（与旧审批 FIELD_CATALOG 对齐）。
"""
from __future__ import annotations

from typing import Any

# biz_type -> [{id, label, type}]。type 仅供前端展示/输入控件选择，条件运算按值比较。
CATALOG: dict[str, list[dict[str, Any]]] = {
    "quote_version": [
        {"id": "amount", "label": "报价金额", "type": "number"},
        {"id": "margin_rate", "label": "毛利率", "type": "number"},
        {"id": "discount_total", "label": "折扣合计", "type": "number"},
    ],
    "contract_version": [
        {"id": "amount", "label": "合同额", "type": "number"},
        {"id": "risk_level", "label": "风险等级", "type": "text"},
    ],
    "change_request": [
        {"id": "change_type", "label": "变更类型", "type": "text"},
        {"id": "cost_impact", "label": "成本影响", "type": "number"},
    ],
    "service_ticket": [
        {"id": "priority", "label": "优先级", "type": "text"},
        {"id": "type", "label": "工单类型", "type": "text"},
    ],
    "order": [
        {"id": "amount", "label": "订单金额", "type": "number"},
    ],
    "lead": [
        {"id": "score", "label": "评分", "type": "number"},
        {"id": "source", "label": "来源", "type": "text"},
        {"id": "customer_type", "label": "客户类型", "type": "text"},
        {"id": "category", "label": "类别", "type": "text"},
        {"id": "country_type", "label": "国内外", "type": "text"},
        {"id": "industry", "label": "行业", "type": "text"},
    ],
    "solution": [],
}


def get_catalog(biz_type: str) -> list[dict[str, Any]]:
    return CATALOG.get(biz_type, [])
