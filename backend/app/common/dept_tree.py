"""部门物化路径(materialized path)的公共工具。

「某部门及其所有下级」在多处需要——用户列表筛选、数据可见范围(data_scope)、
部门→角色规则(dept_role_auto)——统一收敛到这里，避免各写一份而漏掉下面这些坑：

  * 路径为空("")时直接拼 LIKE 会变成 '%'，误命中全租户所有部门
    (Department.path 列默认值就是 "")；
  * 部门名里的 % 和 _ 是 LIKE 通配符，不转义会串到兄弟部门
    ("/研发_一部/" 会把 "/研发X一部/" 也算成自己的子树)；
  * 结尾缺斜杠时 "/研发" 会把 "/研发部/" 误判为下级。

Python 侧前缀匹配用 :func:`subtree_prefix`(不转义)，
SQL 侧 LIKE 用 :func:`subtree_like_pattern`(已转义，需带 ``escape=LIKE_ESCAPE``)。
"""
from sqlalchemy import select

LIKE_ESCAPE = "\\"


def escape_like(value: str) -> str:
    """转义 LIKE 元字符；必须配合 ``.like(..., escape=LIKE_ESCAPE)`` 使用。"""
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def subtree_prefix(path: str | None) -> str | None:
    """把部门物化路径规范成子树前缀；路径缺失/空白时返回 None(表示不可用于前缀匹配)。

    未做 LIKE 转义，供 Python 侧 ``str.startswith`` 使用。
    """
    if not path or not path.strip():
        return None
    return path if path.endswith("/") else path + "/"


def subtree_like_pattern(path: str | None) -> str | None:
    """子树 LIKE 模式(已转义)；路径不合法时返回 None，调用方须跳过而不是退化成 '%'。"""
    prefix = subtree_prefix(path)
    return None if prefix is None else escape_like(prefix) + "%"


def subtree_dept_ids_select(tenant_id: str, dept_ids, dept_paths):
    """构造「这些部门自身 + 其所有下级」的部门 id 查询。

    路径缺失/非法的部门只回落到它自身，绝不退化成「全部部门」；
    部门自身始终按 id 命中，因此历史上没有结尾斜杠的 path 也不会漏掉自己。
    """
    from app.domains.organization.models import Department

    cond = Department.id.in_(list(dept_ids))
    for path in dept_paths:
        pattern = subtree_like_pattern(path)
        if pattern:
            cond = cond | Department.path.like(pattern, escape=LIKE_ESCAPE)
    return select(Department.id).where(Department.tenant_id == tenant_id, cond)
