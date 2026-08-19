"""数据日志 resource 解析。"""
from app.domains.lowcode.wf_field_writeback import audit_resource_for_process


def test_audit_resource_prefers_form_instance():
    rt, rid = audit_resource_for_process(
        form_instance_id="fi-1",
        biz_type=None,
        biz_id=None,
        process_instance_id="pi-1",
    )
    assert rt == "form_instance"
    assert rid == "fi-1"


def test_audit_resource_falls_back_to_biz():
    rt, rid = audit_resource_for_process(
        form_instance_id=None,
        biz_type="lead",
        biz_id="lead-1",
        process_instance_id="pi-1",
    )
    assert rt == "lead"
    assert rid == "lead-1"


def test_audit_resource_falls_back_to_process():
    rt, rid = audit_resource_for_process(
        form_instance_id=None,
        biz_type=None,
        biz_id=None,
        process_instance_id="pi-1",
    )
    assert rt == "wf_process_instance"
    assert rid == "pi-1"
