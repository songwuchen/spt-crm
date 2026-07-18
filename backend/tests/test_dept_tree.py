"""Tests for the shared materialized-path helper (app.common.dept_tree).

「某部门及其所有下级」的前缀匹配以前在三处各写了一份，本模块把它收敛后锁定
三个容易踩的坑：空路径不得退化成匹配全部、LIKE 元字符必须转义、结尾斜杠要规范化。
"""
from app.common.dept_tree import LIKE_ESCAPE, escape_like, subtree_like_pattern, subtree_prefix


# ---- subtree_prefix：Python 侧前缀（不转义）----

def test_prefix_normalizes_trailing_slash():
    assert subtree_prefix("/A/") == "/A/"
    assert subtree_prefix("/A") == "/A/"


def test_prefix_rejects_empty_path():
    # 关键：空路径必须返回 None，调用方据此跳过前缀匹配，
    # 否则 LIKE 会变成 '%' 命中全租户所有部门
    assert subtree_prefix("") is None
    assert subtree_prefix(None) is None
    assert subtree_prefix("   ") is None


# ---- escape_like / subtree_like_pattern：SQL 侧（已转义）----

def test_escape_like_escapes_metacharacters():
    assert escape_like("a_b") == "a\\_b"
    assert escape_like("a%b") == "a\\%b"
    # 反斜杠自身要先转义，否则会把后面的转义符吃掉
    assert escape_like("a\\b") == "a\\\\b"


def test_like_pattern_escapes_department_name_metacharacters():
    # "/研发_一部/" 里的 _ 若不转义会匹配任意单字符，串到 "/研发X一部/"
    assert subtree_like_pattern("/研发_一部/") == "/研发\\_一部/%"
    assert subtree_like_pattern("/A%B/") == "/A\\%B/%"


def test_like_pattern_rejects_empty_path():
    assert subtree_like_pattern("") is None
    assert subtree_like_pattern(None) is None


def test_like_pattern_normalizes_then_escapes():
    assert subtree_like_pattern("/A") == "/A/%"


def test_like_escape_char_is_backslash():
    # 转义字符必须与调用处 .like(..., escape=LIKE_ESCAPE) 一致
    assert LIKE_ESCAPE == "\\"
