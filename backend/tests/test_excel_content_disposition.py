"""excel_response Content-Disposition must be latin-1 safe for Chinese names."""
from __future__ import annotations

from io import BytesIO

from app.common.export import _content_disposition_attachment, excel_response


def test_content_disposition_chinese_filename_is_latin1_safe():
    header = _content_disposition_attachment("收款登记.xlsx")
    header.encode("latin-1")  # must not raise
    assert "filename*=UTF-8''" in header
    assert 'filename="export.xlsx"' in header
    # 不能退化成非法的 ".xlsx"
    assert 'filename=".xlsx"' not in header
    assert "%E6%94%B6" in header


def test_content_disposition_ascii_filename_kept():
    header = _content_disposition_attachment("payment_reg.xlsx")
    assert 'filename="payment_reg.xlsx"' in header
    assert "filename*=UTF-8''payment_reg.xlsx" in header


def test_excel_response_chinese_filename():
    buf = BytesIO(b"PK\x03\x04")
    resp = excel_response(buf, "收款登记.xlsx")
    cd = resp.headers["content-disposition"]
    cd.encode("latin-1")
    assert "attachment" in cd
    assert "filename*=UTF-8''" in cd
    assert 'filename="export.xlsx"' in cd
