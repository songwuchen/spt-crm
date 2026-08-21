# -*- coding: utf-8 -*-
"""通用转交：支持多人。"""
from app.domains.lowcode.workflow_engine import WorkflowEngine


def test_normalize_transfer_targets_single_and_multi():
    assert WorkflowEngine._normalize_transfer_targets(None) == []
    assert WorkflowEngine._normalize_transfer_targets("") == []
    assert WorkflowEngine._normalize_transfer_targets("u1") == ["u1"]
    assert WorkflowEngine._normalize_transfer_targets(["u1", "u2", "u1", "", None]) == ["u1", "u2"]
    assert WorkflowEngine._normalize_transfer_targets(("a", "b")) == ["a", "b"]
