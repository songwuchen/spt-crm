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
        {"id": "amount_total", "label": "合同总金额", "type": "number"},
        {"id": "risk_level", "label": "风险等级", "type": "text"},
        {"id": "change_type", "label": "合同状态(新增/变动)", "type": "text"},
        {"id": "department_id", "label": "部门", "type": "department"},
        {"id": "industry", "label": "行业分类", "type": "text"},
        {"id": "is_export", "label": "设备是否出口", "type": "text"},
        {"id": "standard_delivery", "label": "是否标准交付", "type": "text"},
        {"id": "delivery_mode", "label": "交付方式(YZO/YZS)", "type": "text"},
        {"id": "is_rotary_sieve", "label": "是否为旋振筛", "type": "text"},
        # person：审批抽屉用组织架构选人（写回 user_id，供下一节点 form_field_person 解析）
        {"id": "purchasers", "label": "采购员", "type": "person"},
        {"id": "inspectors", "label": "质检员", "type": "person"},
        {"id": "fill_code", "label": "填写代码", "type": "text"},
        # 财务审核可改（对齐简道云 optAuth）
        {
            "id": "contract_type", "label": "合同类型", "type": "radio",
            "options": [{"value": "正式", "label": "正式"}, {"value": "非正式", "label": "非正式"}],
        },
        {
            "id": "accept_method", "label": "验收方式", "type": "radio",
            "options": [
                {"value": "货到签收", "label": "货到签收"},
                {"value": "指导安装不含验收", "label": "指导安装不含验收"},
                {"value": "货到验收", "label": "货到验收"},
                {"value": "指导安装含验收", "label": "指导安装含验收"},
                {"value": "安装调试", "label": "安装调试"},
            ],
        },
        {"id": "accept_materials", "label": "验收所需资料", "type": "text"},
        {"id": "accept_date", "label": "验收日期", "type": "date"},
        {"id": "contract_id", "label": "合同ID", "type": "text"},
    ],
    "contract_review": [
        {"id": "contract_amount", "label": "合同金额", "type": "number"},
        {"id": "is_export", "label": "是否出口合同", "type": "yes_no"},
        {"id": "need_install", "label": "是否需要安装", "type": "text"},
        {"id": "need_pricing", "label": "是否需要核价", "type": "text"},
        {"id": "department_id", "label": "部门", "type": "department"},
        {"id": "department_name", "label": "业务部门名称", "type": "text"},
        {"id": "owner_id", "label": "业务员", "type": "person"},
        {"id": "region_manager_id", "label": "区域经理/组长", "type": "person"},
        {"id": "customer_type", "label": "客户类型", "type": "text"},
        {"id": "need_feedback", "label": "是否反馈", "type": "yes_no"},
        {"id": "review_type", "label": "评审类型", "type": "text"},
        {"id": "industry", "label": "所属行业", "type": "text"},
        {"id": "clause_opinion", "label": "合同条款审核意见", "type": "textarea"},
        {"id": "legal_risk", "label": "法务风险等级", "type": "risk"},
        {"id": "legal_risk_desc", "label": "法务风险描述", "type": "text"},
        {"id": "tech_risk", "label": "技术风险等级", "type": "risk"},
        {"id": "tech_risk_desc", "label": "技术风险描述", "type": "text"},
        {"id": "biz_risk", "label": "业务风险等级", "type": "risk"},
        {"id": "biz_risk_desc", "label": "业务风险描述", "type": "text"},
        {"id": "finance_risk", "label": "财务风险等级", "type": "risk"},
        {"id": "finance_risk_desc", "label": "财务风险描述", "type": "text"},
        {"id": "purchase_risk", "label": "采购风险等级", "type": "risk"},
        {"id": "purchase_risk_desc", "label": "采购风险描述", "type": "text"},
        {"id": "export_risk", "label": "出口风险等级", "type": "risk"},
        {"id": "export_risk_desc", "label": "出口风险描述", "type": "text"},
        {"id": "payment_term", "label": "账期", "type": "text"},
        {"id": "conclusion", "label": "结论描述", "type": "textarea"},
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
        {"id": "customer_newness", "label": "新/老客户", "type": "text"},
        {"id": "category", "label": "类别", "type": "text"},
        {"id": "country_type", "label": "国内外", "type": "text"},
        {"id": "industry", "label": "行业", "type": "text"},
        # 供抄送/审批人「表单人员字段」解析：审批通过后抄送给线索负责人
        {"id": "owner_id", "label": "负责人", "type": "person"},
        {"id": "reporter_id", "label": "报备人", "type": "person"},
        {"id": "department_id", "label": "部门", "type": "department"},
    ],
    "solution": [
        {"id": "solution_no", "label": "方案编号", "type": "text"},
        {"id": "status", "label": "状态", "type": "text"},
        {"id": "assignee_id", "label": "负责人", "type": "person"},
        {"id": "assignee_name", "label": "负责人姓名", "type": "text"},
        {"id": "department_id", "label": "部门", "type": "department"},
        {"id": "department_name", "label": "部门名称", "type": "text"},
        {"id": "current_version_no", "label": "当前版本号", "type": "number"},
        {"id": "created_by_id", "label": "创建人", "type": "person"},
        {"id": "project_id", "label": "商机ID", "type": "text"},
    ],
}


def get_catalog(biz_type: str) -> list[dict[str, Any]]:
    return CATALOG.get(biz_type, [])
