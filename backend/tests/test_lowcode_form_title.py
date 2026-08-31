"""表单实例/审批标题组合规则回归。"""
from app.domains.lowcode._presale_service_notice_generated import PRESALE_SERVICE_NOTICE_JDY
from app.domains.lowcode.service import (
    derive_form_instance_title,
    is_weak_form_title,
    _is_presale_template,
)

_PRESALE_DEFS = PRESALE_SERVICE_NOTICE_JDY["presale_service_notice"]["field_definitions"]


def test_presale_composite_title_with_resolved_refs():
    data = {
        "serial_no": "24.13-202608194770",
        "service_location": "乌鲁木齐",
        "contract_no": "11111111-1111-4111-8111-111111111111",
        "applicant": "22222222-2222-4222-8222-222222222222",
    }
    labels = {
        "11111111-1111-4111-8111-111111111111": "HJ20260817003",
        "22222222-2222-4222-8222-222222222222": "张三",
    }
    title = derive_form_instance_title("售前服务通知", data, _PRESALE_DEFS, labels)
    assert title == "售前服务通知: 24.13-202608194770 · 乌鲁木齐 · HJ20260817003 · 张三"
    assert not is_weak_form_title(title, "售前服务通知")


def test_presale_weak_title_only_template_name():
    assert is_weak_form_title("售前服务通知", "售前服务通知")
    title = derive_form_instance_title(
        "售前服务通知",
        {"service_location": "上海"},
        _PRESALE_DEFS,
    )
    assert title == "售前服务通知: 上海"
    assert not is_weak_form_title(title, "售前服务通知")


def test_presale_detected_by_field_defs():
    assert _is_presale_template(None, _PRESALE_DEFS)


def test_prod_card_title_from_contract_no_select():
    """生产卡选合同路径：标题应带出合同图纸号，避免待办列表仅显示模板名。"""
    data = {"contract_no_select": "6dafebcf-70fc-4020-886f-b976ceb7afa9"}
    labels = {"6dafebcf-70fc-4020-886f-b976ceb7afa9": "WMGF202607130"}
    title = derive_form_instance_title("生产卡/补充流程", data, None, labels)
    assert title == "生产卡/补充流程: WMGF202607130"
    assert not is_weak_form_title(title, "生产卡/补充流程")
