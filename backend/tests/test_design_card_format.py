"""新设计卡号格式：部门编号-yyyyMMdd+两位日序。"""
from app.domains.lowcode.serial_number import format_serial_date, _parse_form_date


def test_design_card_no_example_format():
    dt = _parse_form_date("2026-08-06 10:00:00")
    assert dt is not None
    date_part = format_serial_date("yyyyMMdd", dt)
    assert date_part == "20260806"
    assert f"03-{date_part}01" == "03-2026080601"
