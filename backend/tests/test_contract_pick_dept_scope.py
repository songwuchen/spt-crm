"""合同选择：多部门过滤逻辑。"""
from app.domains.lowcode.contract_pick_scope import resolve_pick_department_ids


def test_multi_dept_user_uses_union_not_form_only():
    """岳毅类用户：不能只看表单里一个所在部门。"""
    user_depts = ["dept-mkt", "dept-sales", "dept-qing"]
    assert resolve_pick_department_ids(
        scope_all=False,
        user_department_ids=user_depts,
        department_id="dept-mkt",
    ) == user_depts


def test_single_dept_user_uses_form_department():
    assert resolve_pick_department_ids(
        scope_all=False,
        user_department_ids=["dept-a"],
        department_id="dept-a",
    ) == ["dept-a"]


def test_all_scope_no_filter():
    assert resolve_pick_department_ids(
        scope_all=True,
        user_department_ids=["dept-a"],
        department_id="dept-a",
    ) is None


def test_id_lookup_skips_dept_filter():
    assert resolve_pick_department_ids(
        scope_all=False,
        user_department_ids=["dept-a"],
        department_id="dept-a",
        for_id_lookup=True,
    ) is None


def test_invoice_purpose_implies_scope_all():
    """开票选合同：purpose=invoice_application 时按 scope_all 不过滤部门。"""
    assert resolve_pick_department_ids(
        scope_all=True,  # router 对 invoice_application 强制
        user_department_ids=["dept-a"],
        department_id="dept-a",
    ) is None


def test_explicit_department_ids_intersect_user():
    assert resolve_pick_department_ids(
        scope_all=False,
        user_department_ids=["dept-a", "dept-b"],
        department_ids=["dept-b", "dept-x"],
    ) == ["dept-b"]


def test_form_dept_outside_user_tree_falls_back():
    assert resolve_pick_department_ids(
        scope_all=False,
        user_department_ids=["dept-a"],
        department_id="dept-other",
    ) == ["dept-a"]
