"""阿里云 IMM WebOffice 在线文档预览（对齐 spt-lowcode）。

覆盖本地渲染不了的格式：.doc / .ppt / .pptx / .wps / .xls / .xlsx …
pdf / docx / txt / csv 仍走本地渲染——免费、内网可用、不把文档送出。

流程：
  后端 GenerateWebofficeToken(SourceURI=oss://bucket/key) → {url, access_token, refresh_token}
  前端 aliyun-web-office-sdk 挂 iframe + setToken；到期 refresh。

前提：附件在阿里云 OSS；IMM 项目名可在「系统设置 → 文件存储」配置（也可用环境变量兜底）。
未开通时接口返回 enabled=false，前端退回本地预览或下载。
"""
from __future__ import annotations

import re
from typing import Any

from app.common.exceptions import BusinessException

WEBOFFICE_EXTS = {
    "doc", "docx", "txt", "dot", "wps", "wpt", "dotx", "docm", "dotm", "rtf",
    "ppt", "pptx", "pptm", "ppsx", "ppsm", "pps", "potx", "potm", "dpt", "dps",
    "et", "xls", "xlt", "xlsx", "xlsm", "xltx", "xltm", "csv",
    "pdf",
}

LOCAL_RENDERED_EXTS = {"pdf", "docx", "csv", "txt", "md", "log"}

SHEET_FALLBACK_EXTS = frozenset({"xls", "xlsx", "xlsm"})
PPTX_FALLBACK_EXTS = frozenset({"pptx"})


def file_ext(name: str | None) -> str:
    n = name or ""
    return n.rsplit(".", 1)[-1].lower() if "." in n else ""


def needs_weboffice(name: str | None) -> bool:
    ext = file_ext(name)
    return ext in WEBOFFICE_EXTS and ext not in LOCAL_RENDERED_EXTS


def is_imm_configured(imm: dict | None) -> bool:
    """imm: {enabled?, project, region?, endpoint?}；enabled 显式 False 时关闭。"""
    imm = imm or {}
    if imm.get("enabled") is False:
        return False
    return bool((imm.get("project") or "").strip())


def _region(imm: dict, oss_endpoint: str) -> str:
    if (imm.get("region") or "").strip():
        return imm["region"].strip()
    m = re.search(r"oss-([a-z0-9-]+)\.", oss_endpoint or "")
    return m.group(1) if m else "cn-hangzhou"


def _imm_endpoint(imm: dict, oss_endpoint: str) -> str:
    if (imm.get("endpoint") or "").strip():
        return imm["endpoint"].strip()
    return f"imm.{_region(imm, oss_endpoint)}.aliyuncs.com"


def _client(access_key: str, secret_key: str, imm: dict, oss_endpoint: str):
    from alibabacloud_imm20200930.client import Client
    from alibabacloud_tea_openapi import models as open_api_models

    return Client(open_api_models.Config(
        access_key_id=access_key,
        access_key_secret=secret_key,
        endpoint=_imm_endpoint(imm, oss_endpoint),
    ))


def _to_dict(body: Any) -> dict:
    return {
        "url": body.weboffice_url,
        "access_token": body.access_token,
        "refresh_token": body.refresh_token,
        "access_token_expired_time": body.access_token_expired_time,
        "refresh_token_expired_time": body.refresh_token_expired_time,
    }


def _err_text(e: Exception) -> str:
    msg = getattr(e, "message", None) or str(e)
    data = getattr(e, "data", None)
    if isinstance(data, dict) and data.get("Message"):
        msg = data["Message"]
    return str(msg)[:200]


def generate(
    *,
    imm: dict,
    access_key: str,
    secret_key: str,
    bucket: str,
    endpoint: str,
    storage_key: str,
    filename: str,
    user_id: str = "",
    user_name: str = "",
    allow_download: bool = True,
) -> dict:
    if not is_imm_configured(imm):
        raise BusinessException(message="未配置在线文档预览服务（IMM）")
    if not (access_key and secret_key and bucket):
        raise BusinessException(message="OSS 凭证不完整，无法签发 WebOffice 预览")

    from alibabacloud_imm20200930 import models as imm_models

    project = (imm.get("project") or "").strip()
    req = imm_models.GenerateWebofficeTokenRequest(
        project_name=project,
        source_uri=f"oss://{bucket}/{storage_key}",
        filename=filename or "document",
        hidecmb=True,
        permission=imm_models.WebofficePermission(
            readonly=True,
            copy=allow_download,
            export=allow_download,
            print=allow_download,
            history=False,
            rename=False,
        ),
        user=imm_models.WebofficeUser(id=user_id or "preview", name=user_name or "预览用户"),
    )
    try:
        resp = _client(access_key, secret_key, imm, endpoint).generate_weboffice_token(req)
    except Exception as e:  # noqa: BLE001
        raise BusinessException(message=f"在线预览服务调用失败：{_err_text(e)}") from e
    return _to_dict(resp.body)


def refresh(
    *,
    imm: dict,
    access_key: str,
    secret_key: str,
    endpoint: str,
    access_token: str,
    refresh_token: str,
) -> dict:
    if not is_imm_configured(imm):
        raise BusinessException(message="未配置在线文档预览服务（IMM）")

    from alibabacloud_imm20200930 import models as imm_models

    req = imm_models.RefreshWebofficeTokenRequest(
        project_name=(imm.get("project") or "").strip(),
        access_token=access_token,
        refresh_token=refresh_token,
    )
    try:
        resp = _client(access_key, secret_key, imm, endpoint).refresh_weboffice_token(req)
    except Exception as e:  # noqa: BLE001
        raise BusinessException(message=f"预览凭证续期失败：{_err_text(e)}") from e
    body = resp.body
    return {
        "url": None,
        "access_token": body.access_token,
        "refresh_token": body.refresh_token,
        "access_token_expired_time": body.access_token_expired_time,
        "refresh_token_expired_time": body.refresh_token_expired_time,
    }
