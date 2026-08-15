"""按模块数据范围：可配置 biz_type 清单（前后端对齐）。

未在明细中覆盖的模块，仍走角色默认 data_scope。
联系人无独立键：可见性跟随客户（visible_customer_ids_select）。
"""

from __future__ import annotations

# (key, label, group) — key 写入 roles.scope_by_resource
SCOPE_MODULE_DEFS: tuple[tuple[str, str, str], ...] = (
    ("customer", "客户", "主数据"),
    ("lead", "线索", "销售"),
    ("project", "商机", "销售"),
    ("quote", "报价", "销售"),
    ("contract", "合同", "销售"),
    ("solution", "方案", "销售"),
    ("tender", "标书", "销售"),
    ("order", "订单", "销售"),
    ("delivery", "交付", "履约"),
    ("payment", "回款", "履约"),
    ("change", "变更", "履约"),
    ("service", "工单", "售后与协作"),
    ("task", "任务", "售后与协作"),
)

SCOPE_MODULE_KEYS = frozenset(k for k, _, _ in SCOPE_MODULE_DEFS)

# 商机子单据：列表/详情用独立 biz_type 解析 owner 范围；ACL/成员仍跟商机
PROJECT_CHILD_BIZ_TYPES = frozenset({
    "quote", "contract", "solution", "delivery", "payment", "change",
})
