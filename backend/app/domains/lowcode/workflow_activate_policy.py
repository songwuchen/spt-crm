# -*- coding: utf-8 -*-
"""流程「激活/重开」策略：生产卡补充流程放宽权限与进行中可激活。"""

from __future__ import annotations

PROD_CARD_SUPPLEMENT_PROCESS_CODE = "SYS_PROD_CARD_SUPPLEMENT"

_DEFAULT_ACTIVATABLE = frozenset({"completed", "rejected", "withdrawn"})


def activatable_statuses(process_code: str | None) -> frozenset[str]:
    """按流程类型返回允许激活的实例状态。"""
    if process_code == PROD_CARD_SUPPLEMENT_PROCESS_CODE:
        return _DEFAULT_ACTIVATABLE | {"running"}
    return _DEFAULT_ACTIVATABLE


def is_open_activate_process(process_code: str | None) -> bool:
    """是否对任意登录用户开放激活（无需 workflow:activate）。"""
    return process_code == PROD_CARD_SUPPLEMENT_PROCESS_CODE
