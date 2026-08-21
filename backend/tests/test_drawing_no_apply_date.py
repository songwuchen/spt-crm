"""图纸编号取号日与订货日脱钩。"""
from datetime import date

from app.domains.contract.service import (
    _coerce_drawing_apply_date,
    drawing_no_apply_date_today,
)


def test_drawing_apply_date_defaults_to_today():
    today = drawing_no_apply_date_today()
    assert _coerce_drawing_apply_date(None) == today.isoformat()
    assert _coerce_drawing_apply_date("") == today.isoformat()


def test_drawing_apply_date_accepts_explicit_day():
    assert _coerce_drawing_apply_date(date(2026, 8, 21)) == "2026-08-21"
    assert _coerce_drawing_apply_date("2026-08-21") == "2026-08-21"
