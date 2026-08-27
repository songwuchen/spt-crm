"""技术协议评审字段 label 映射（数据日志 / 审批写回展示）。"""

TAR_FIELD_LABELS: dict[str, str] = {
    "review_code": "流水号",
    "status": "流程状态",
    "company_name": "公司名称",
    "customer_id": "客户",
    "applicant_id": "申请人",
    "applicant_name": "申请人",
    "apply_at": "日期时间",
    "owner_id": "业务员",
    "owner_name": "业务员",
    "department_id": "业务部门",
    "department_name": "业务部门",
    "industry": "所属行业",
    "address": "地址",
    "elec_ctrl": "电控装置",
    "project_title": "项目名称及应用",
    "has_weight_req": "是否有重量要求",
    "use_idle_equip": "是否趁用呆滞设备",
    "has_smart": "合同是否含智能化部分",
    "need_pricing": "是否核价",
    "sign_basis": "合同签订依据及情况",
    "ref_contract_no": "参考合同号",
    "pre_contact": "前期沟通人",
    "remark": "备注",
    "has_objection": "是否有异议",
    "design_approver_ids": "设计审批",
    "design_approver_2_ids": "设计审批2",
    "form_json.design_approver_ids": "设计审批",
    "form_json.design_approver_2_ids": "设计审批2",
}


def tar_field_labels() -> dict[str, str]:
    return dict(TAR_FIELD_LABELS)
