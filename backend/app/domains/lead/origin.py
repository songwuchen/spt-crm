"""线索来源：简道云迁移 vs CRM 自建（靠编号格式区分）。"""
from __future__ import annotations

import re

# 简道云申报信息流水号：申报信息-yyyyMMdd + 序号
_JDY_NEW = re.compile(r"^申报信息-\d")
# 简道云旧版/过渡编号（app 版本前缀等）
_JDY_APP_PREFIX = re.compile(r"^\d+\.\d+\.\d+-")
# 简道云更早期：2021-01-001
_JDY_LEGACY = re.compile(r"^\d{4}-\d{2}-\d+")
# CRM 自建：YYYYMM + 3 位月序，纯数字 9 位
_CRM_NATIVE = re.compile(r"^\d{9}$")


def is_jdy_lead_code(code: str | None) -> bool:
    """编号来自简道云申报信息（含迁移保留原号）。"""
    s = (code or "").strip()
    if not s:
        return False
    return bool(_JDY_NEW.match(s) or _JDY_APP_PREFIX.match(s) or _JDY_LEGACY.match(s))


def is_crm_native_lead_code(code: str | None) -> bool:
    """编号由 CRM 自增规则生成（YYYYMM###）。"""
    s = (code or "").strip()
    return bool(s and _CRM_NATIVE.match(s))


def lead_code_origin(code: str | None) -> str:
    """返回 'jdy' | 'crm' | 'unknown'。"""
    if is_jdy_lead_code(code):
        return "jdy"
    if is_crm_native_lead_code(code):
        return "crm"
    return "unknown"
