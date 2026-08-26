"""表单列表：submitted + 进行中流程应展示当前节点与审批中。"""
from datetime import datetime, timezone

from app.domains.lowcode.router import _inst_list_dict


def _fake_fi(**kw):
    base = {
        "id": "fi1",
        "template_id": "tpl1",
        "initiator_id": "u1",
        "created_at": datetime.now(timezone.utc),
        "form_data": {},
        "status": "submitted",
    }
    base.update(kw)
    return type("FI", (), base)()


def test_inst_list_dict_submitted_with_running_node_shows_running():
    d = _inst_list_dict(_fake_fi(), {}, "物料编码")
    assert d["current_node_name"] == "物料编码"
    assert d["status"] == "running"


def test_inst_list_dict_submitted_without_node_keeps_submitted():
    d = _inst_list_dict(_fake_fi(), {}, None)
    assert d["status"] == "submitted"
    assert not d.get("current_node_name")
