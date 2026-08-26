# -*- coding: utf-8 -*-
"""收款登记抄送通知：对齐简道云 OA 卡摘要字段。"""
from __future__ import annotations

from app.domains.lowcode.wf_notify import _CC_NOTIFY_FIELD_PREFS


def test_payment_registration_cc_field_prefs_order():
    prefs = _CC_NOTIFY_FIELD_PREFS["payment_registration"]
    labels = [p[1] for p in prefs]
    assert labels == [
        "来款日期",
        "单位名称",
        "部门",
        "来款合计",
    ]
