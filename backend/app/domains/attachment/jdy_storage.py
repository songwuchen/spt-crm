"""简道云历史附件 OSS（只读）。

迁移数据中的附件引用可使用 ``jdy-oss:{base64url(oss_key)}`` 作为虚拟 id，
通过租户「简道云 OSS」配置签发预签名链接阅览/下载。
"""
from __future__ import annotations

import base64
import re

JDY_OSS_PREFIX = "jdy-oss:"
JDY_META_PREFIX = "jdy-meta:"


def jdy_attachment_id_from_key(oss_key: str) -> str:
    key = (oss_key or "").strip().lstrip("/")
    if not key:
        raise ValueError("empty oss key")
    b64 = base64.urlsafe_b64encode(key.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{JDY_OSS_PREFIX}{b64}"


def parse_jdy_attachment_id(attachment_id: str | None) -> str | None:
    """从虚拟附件 id 解析 OSS object key；非 jdy-oss 前缀返回 None。"""
    if not attachment_id or not attachment_id.startswith(JDY_OSS_PREFIX):
        return None
    b64 = attachment_id[len(JDY_OSS_PREFIX):]
    if not b64:
        return None
    pad = "=" * (-len(b64) % 4)
    try:
        return base64.urlsafe_b64decode(b64 + pad).decode("utf-8")
    except Exception:
        return None


def is_jdy_oss_attachment_id(attachment_id: str | None) -> bool:
    return parse_jdy_attachment_id(attachment_id) is not None


def filename_from_oss_key(oss_key: str) -> str:
    """从 OSS key 末段提取展示文件名（对齐 jdy-wrapper 归档命名）。"""
    base = oss_key.rsplit("/", 1)[-1]
    # datahub/{app}/{entry}/{qiniuKey}_{safeName}
    m = re.match(r"^[^_]+_(.+)$", base)
    if m:
        return m.group(1) or base
    return base or "file"
