"""表单列表数据范围：核价清单按业务部门/申请人字段匹配部门档；报价以单据部门为准。"""
from app.domains.lowcode.service import (
    _FORM_DEPT_FIELDS_BY_TEMPLATE,
    _FORM_DEPT_NAME_FIELDS_BY_TEMPLATE,
    _FORM_DEPT_PRIMARY_TEMPLATES,
    _OWNER_PERSON_FIELDS_BY_TEMPLATE,
    _instance_list_conds,
    _form_data_text_in_literals,
)


def test_pricing_checklist_scope_field_maps():
    assert "pricing_checklist_hjqd" in _OWNER_PERSON_FIELDS_BY_TEMPLATE
    assert "business_dept" in _FORM_DEPT_NAME_FIELDS_BY_TEMPLATE["pricing_checklist_hjqd"]
    assert "install_department" in _FORM_DEPT_FIELDS_BY_TEMPLATE["pricing_checklist_hjqd"]


def test_quote_management_dept_primary_maps():
    assert "quote_management" in _FORM_DEPT_PRIMARY_TEMPLATES
    assert "department" in _FORM_DEPT_FIELDS_BY_TEMPLATE["quote_management"]
    assert "sales_person" in _OWNER_PERSON_FIELDS_BY_TEMPLATE["quote_management"]


def test_payment_registration_dept_primary_maps():
    assert "payment_registration" in _FORM_DEPT_PRIMARY_TEMPLATES
    assert "department" in _FORM_DEPT_FIELDS_BY_TEMPLATE["payment_registration"]
    assert "sales_person" in _OWNER_PERSON_FIELDS_BY_TEMPLATE["payment_registration"]


def test_instance_list_conds_includes_dept_and_name_clauses():
    conds = _instance_list_conds(
        "t1", "tpl1",
        owner_ids=["u-sales"],
        owner_person_fields=["install_applicant"],
        template_code="pricing_checklist_hjqd",
        form_dept_scope_ids=["dept-a"],
        form_dept_name_literals=["精细筛分装备销售事业部"],
    )
    assert len(conds) >= 2
    owner_cond = conds[-1]
    # SQLAlchemy BinaryExpression — ensure OR expanded (not just initiator)
    compiled = str(owner_cond.compile(compile_kwargs={"literal_binds": True}))
    assert "initiator_id" in compiled
    assert "install_applicant" in compiled
    assert "install_department" in compiled
    assert "business_dept" in compiled


def test_quote_dept_primary_does_not_leak_by_teammate_initiator():
    """部门档报价：同事跨事业部开单（部门=外部门）不应仅因发起人在本部门而可见。"""
    conds = _instance_list_conds(
        "t1", "tpl-quote",
        owner_ids=["u-duan", "u-teammate"],
        owner_person_fields=["sales_person"],
        template_code="quote_management",
        form_dept_scope_ids=["dept-xjwm"],
        scope_viewer_id="u-duan",
    )
    owner_cond = conds[-1]
    compiled = str(owner_cond.compile(compile_kwargs={"literal_binds": True}))
    assert "department" in compiled
    assert "u-duan" in compiled
    # 本人参与仍可见；外部门靠 department 命中，不靠 teammate 发起人放大
    assert "sales_person" in compiled


def test_payment_registration_dept_primary_scope():
    """部门档收款登记：按单据部门可见，本人发起/业务人员仍可见。"""
    conds = _instance_list_conds(
        "t1", "tpl-pay",
        owner_ids=["u-mkt-a", "u-mkt-b"],
        owner_person_fields=["sales_person"],
        template_code="payment_registration",
        form_dept_scope_ids=["dept-mkt"],
        scope_viewer_id="u-mkt-a",
    )
    owner_cond = conds[-1]
    compiled = str(owner_cond.compile(compile_kwargs={"literal_binds": True}))
    assert "department" in compiled
    assert "sales_person" in compiled
    assert "u-mkt-a" in compiled


def test_instance_list_conds_workflow_participant_or():
    """数据范围受限时，仍可通过流程参与旁路看到单据。"""
    conds = _instance_list_conds(
        "t1", "tpl-pc",
        owner_ids=["u-other"],
        template_code="prod_card_supplement",
        workflow_participant_user_id="u-approver",
    )
    owner_cond = conds[-1]
    compiled = str(owner_cond.compile(compile_kwargs={"literal_binds": True}))
    assert "initiator_id" in compiled
    assert "wf_process_instance" in compiled or "EXISTS" in compiled.upper()


def test_form_data_text_in_literals_builds_or():
    clause = _form_data_text_in_literals("business_dept", ["冶金矿山"])
    assert clause is not False
