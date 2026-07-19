"""导出路径的脱敏必须覆盖全部 mask_type。

回归：PDF 导出曾只判断值是否等于 "***"，判断完又回头去读未脱敏的模型属性 ——
于是 mask_type=null / zero 两种策略下导出仍打印真值，页面显示脱敏、导出泄露。
"""
import pytest

from app.common.field_mask import DEFAULT_MASK_POLICIES, apply_field_mask, masked_number


@pytest.mark.parametrize("mask_type,masked_cell,expected_pdf", [
    ("hidden", "***", None),   # 值被替换成哨兵 → 数值渲染取不到 → 不输出
    ("null", None, None),      # 值被置空 → 不输出
    ("zero", 0, 0.0),          # 值被置 0 → 输出 0，这正是该策略的意图
])
def test_masked_number_handles_every_mask_type(mask_type, masked_cell, expected_pdf):
    assert masked_number(masked_cell) == expected_pdf
    assert mask_type  # 参数名仅用于可读性


def test_masked_number_passes_through_real_values():
    assert masked_number(1234.5) == 1234.5
    assert masked_number("1234.5") == 1234.5
    assert masked_number(0) == 0.0          # 0 是合法金额，不能当成脱敏
    assert masked_number(None, 0.0) == 0.0  # default 生效


@pytest.mark.parametrize("mask_type", ["hidden", "null", "zero"])
def test_apply_field_mask_then_masked_number_never_leaks(mask_type):
    """把两步串起来验证：任何 mask_type 下都拿不到真实值 4321。"""
    policies = [{"resource": "contract", "field": "amount_total",
                 "required_permission": "contract:view_amount", "mask_type": mask_type}]
    masked = apply_field_mask({"amount_total": 4321.0}, "contract", [], policies)
    assert masked_number(masked["amount_total"]) != 4321.0

    # 有权限者仍拿到真实值
    allowed = apply_field_mask({"amount_total": 4321.0}, "contract",
                               ["contract:view_amount"], policies)
    assert masked_number(allowed["amount_total"]) == 4321.0


def test_default_policies_are_all_hidden_type():
    """默认策略若引入 null/zero，上面的导出路径也必须一并复查。"""
    assert {p["mask_type"] for p in DEFAULT_MASK_POLICIES} == {"hidden"}
