"""Unit tests for IMM WebOffice preview routing helpers."""

from app.domains.attachment.weboffice_service import needs_weboffice, file_ext, LOCAL_RENDERED_EXTS


def test_needs_weboffice_legacy_doc():
    assert needs_weboffice("a.doc") is True
    assert needs_weboffice("A.DOC") is True
    assert needs_weboffice("deck.ppt") is True
    assert needs_weboffice("deck.pptx") is True
    assert needs_weboffice("sheet.xlsx") is True


def test_local_formats_skip_weboffice():
    assert needs_weboffice("a.docx") is False
    assert needs_weboffice("a.pdf") is False
    assert needs_weboffice("a.txt") is False
    assert file_ext("x.DocX") == "docx"
    assert "docx" in LOCAL_RENDERED_EXTS


def test_is_imm_configured():
    from app.domains.attachment.weboffice_service import is_imm_configured
    assert is_imm_configured({"enabled": True, "project": "p1"}) is True
    assert is_imm_configured({"enabled": False, "project": "p1"}) is False
    assert is_imm_configured({"project": ""}) is False
    assert is_imm_configured({"project": "p1"}) is True
