# -*- coding: utf-8 -*-
from app.domains.lowcode.workflow_activate_policy import (
    PROD_CARD_SUPPLEMENT_PROCESS_CODE,
    activatable_statuses,
    is_open_activate_process,
)


def test_activatable_statuses_default():
    assert activatable_statuses("SYS_QUOTE") == frozenset({"completed", "rejected", "withdrawn"})


def test_activatable_statuses_prod_card_includes_running():
    statuses = activatable_statuses(PROD_CARD_SUPPLEMENT_PROCESS_CODE)
    assert "running" in statuses
    assert "completed" in statuses


def test_is_open_activate_process_prod_card_only():
    assert is_open_activate_process(PROD_CARD_SUPPLEMENT_PROCESS_CODE) is True
    assert is_open_activate_process("SYS_QUOTE") is False
