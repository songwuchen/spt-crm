"""线索编号来源识别。"""
from app.domains.lead.origin import is_crm_native_lead_code, is_jdy_lead_code, lead_code_origin


def test_jdy_lead_codes():
    assert is_jdy_lead_code("申报信息-2025121274320")
    assert is_jdy_lead_code("24.23.1-2023032753065")
    assert is_jdy_lead_code("2021-01-001")
    assert not is_jdy_lead_code("202608001")


def test_crm_native_lead_codes():
    assert is_crm_native_lead_code("202608001")
    assert is_crm_native_lead_code("202512099")
    assert not is_crm_native_lead_code("申报信息-2025121274320")


def test_lead_code_origin():
    assert lead_code_origin("申报信息-2025121274320") == "jdy"
    assert lead_code_origin("202608001") == "crm"
    assert lead_code_origin("CUSTOM-X") == "unknown"
