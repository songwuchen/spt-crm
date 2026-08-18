"""表单列表数据范围：核价清单按业务部门/申请人字段匹配部门档。"""
from app.domains.lowcode.service import (
    _FORM_DEPT_FIELDS_BY_TEMPLATE,
    _FORM_DEPT_NAME_FIELDS_BY_TEMPLATE,
    _OWNER_PERSON_FIELDS_BY_TEMPLATE,
    _instance_list_conds,
    _form_data_text_in_literals,
)


def test_pricing_checklist_scope_field_maps():
    assert "pricing_checklist_hjqd" in _OWNER_PERSON_FIELDS_BY_TEMPLATE
    assert "business_dept" in _FORM_DEPT_NAME_FIELDS_BY_TEMPLATE["pricing_checklist_hjqd"]
    assert "install_department" in _FORM_DEPT_FIELDS_BY_TEMPLATE["pricing_checklist_hjqd"]


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


def test_form_data_text_in_literals_builds_or():
    clause = _form_data_text_in_literals("business_dept", ["冶金矿山"])
    assert clause is not False
