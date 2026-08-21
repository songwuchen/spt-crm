import asyncio
import os
import time
import uuid
import urllib.parse
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Request, Query
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_tenant_id, require_permissions, get_current_user
from app.common.schemas import ok
from app.common.exceptions import BusinessException
from app.common.error_codes import UNAUTHORIZED, FORBIDDEN, NOT_FOUND
from app.domains.attachment import service
from app.domains.attachment.storage import get_full_path, build_object_key, StorageError
from app.domains.lowcode import workflow_service as wsvc

router = APIRouter(prefix="/api/v1/attachments", tags=["附件管理"])

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB（含 MP4 等视频；与前端 FileField 一致）
ALLOWED_EXTENSIONS = {
    # 图片
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.svg',
    # 办公文档 / 电子发票
    '.pdf', '.ofd', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.rtf',
    # 压缩包
    '.zip', '.rar', '.7z',
    # 视频
    '.mp4', '.mov', '.avi', '.wmv', '.mkv', '.webm', '.m4v', '.flv',
    '.mpeg', '.mpg', '.3gp',
    # CAD / 工程图（报价询价单附件常用）
    '.dwg', '.dxf', '.dwt', '.dwf', '.dwfx',
    '.step', '.stp', '.iges', '.igs',
    '.sldprt', '.sldasm', '.slddrw',
    '.ipt', '.iam', '.idw',
    '.catpart', '.catproduct', '.catdrawing',
    '.prt', '.asm', '.x_t', '.x_b',
    '.stl', '.obj', '.3ds', '.parasolid',
    # 其它常见附图
    '.vsd', '.vsdx', '.eml', '.msg',
}
ALLOWED_MIME_PREFIXES = {
    'image/', 'video/',
    'application/pdf', 'application/ofd', 'application/vnd.ofd',
    'application/msword',
    'application/vnd.openxmlformats', 'application/vnd.ms-',
    'text/plain', 'text/csv', 'text/rtf', 'application/rtf',
    'application/zip', 'application/x-rar', 'application/x-7z',
    'application/octet-stream',  # generic fallback for zip/rar/CAD
    # AutoCAD / 通用 CAD
    'application/acad', 'application/x-acad', 'application/autocad',
    'application/x-autocad', 'application/dwg', 'application/x-dwg',
    'image/vnd.dwg', 'image/x-dwg', 'application/dxf', 'application/x-dxf',
    'model/step', 'application/step', 'application/sla', 'model/stl',
    'application/vnd.visio', 'message/rfc822',
}

PRESIGN_EXPIRES = 600  # 10 minutes


def _is_contract_attachment_biz(biz_type: str | None) -> bool:
    """合同本体及合同登记附件槽位（contract_agreement / contract_image / …）。"""
    bt = biz_type or ""
    if bt.startswith("contract_review") or bt.startswith("tech_agreement_review"):
        return False
    return bt == "contract" or bt.startswith("contract_")


def _wf_biz_for_attachment_slot(biz_type: str | None) -> str | None:
    """附件槽位 → 流程实例 biz_type（合同评审 / 技术协议评审）。"""
    bt = biz_type or ""
    if bt.startswith("contract_review"):
        return "contract_review"
    if bt.startswith("tech_agreement_review"):
        return "tech_agreement_review"
    return None


async def _can_download_via_wf(
    db: AsyncSession,
    tenant_id: str,
    user_id: str | None,
    *,
    biz_type: str | None = None,
    biz_id: str | None = None,
    attachment_id: str | None = None,
) -> bool:
    """审批相关人可只读附件（不必有 attachment:download）。

    覆盖：合同登记、合同/技术协议评审、低代码表单流程（form_data 内 file/image 引用）。
    """
    if not user_id:
        return False
    from sqlalchemy import String, cast, select
    from app.domains.attachment.models import AttachmentLink
    from app.domains.lowcode.models import FormInstance

    contract_ids: set[str] = set()
    review_pairs: set[tuple[str, str]] = set()  # (process_biz_type, biz_id)

    def _collect(bt: str | None, bid: str | None) -> None:
        if not bt or not bid:
            return
        if _is_contract_attachment_biz(bt):
            contract_ids.add(bid)
            return
        proc = _wf_biz_for_attachment_slot(bt)
        if proc:
            review_pairs.add((proc, bid))

    _collect(biz_type, biz_id)
    if attachment_id:
        links = (await db.execute(
            select(AttachmentLink.biz_type, AttachmentLink.biz_id).where(
                AttachmentLink.tenant_id == tenant_id,
                AttachmentLink.attachment_id == attachment_id,
            )
        )).all()
        for bt, bid in links:
            _collect(bt, bid)
        # 低代码表单：附件 id 写在 form_data（含明细子表 image/file 列）而非 attachment_links
        form_ids = (await db.execute(
            select(FormInstance.id).where(
                FormInstance.tenant_id == tenant_id,
                FormInstance.is_deleted.is_(False),  # noqa: E712
                cast(FormInstance.form_data, String).contains(attachment_id),
            ).limit(20)
        )).scalars().all()
        for fid in form_ids:
            if await wsvc.can_access_form_via_workflow(db, tenant_id, user_id, fid):
                return True

    for cid in contract_ids:
        if await wsvc.can_access_contract_via_workflow(
            db, tenant_id, user_id, contract_id=cid,
        ):
            return True
    for proc_bt, bid in review_pairs:
        if await wsvc.can_access_biz_via_workflow(
            db, tenant_id, user_id, biz_type=proc_bt, biz_id=bid,
        ):
            return True
    return False


async def _require_attachment_download_or_wf(
    db: AsyncSession,
    tenant_id: str,
    current_user: dict,
    *,
    biz_type: str | None = None,
    biz_id: str | None = None,
    attachment_id: str | None = None,
) -> bool:
    """有 attachment:download，或流程审批相关人；返回是否走审批旁路（跳过数据范围）。"""
    via_wf = await _can_download_via_wf(
        db, tenant_id, current_user.get("sub"),
        biz_type=biz_type, biz_id=biz_id, attachment_id=attachment_id,
    )
    if via_wf:
        return True
    perms = current_user.get("permissions") or []
    if "attachment:download" in perms:
        return False
    raise BusinessException(code=FORBIDDEN, message="缺少权限: attachment:download")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不支持的文件类型: {ext}")
    return ext


def _validate_mime(content_type: Optional[str]) -> None:
    ct = (content_type or "").lower().split(";")[0].strip()
    if not ct or ct == "application/octet-stream":
        return
    if any(ct.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        return
    raise BusinessException(message=f"不支持的内容类型: {ct}")


def _validate_upload_type(filename: str, content_type: Optional[str]) -> str:
    """扩展名白名单为主；MIME 辅助（CAD 浏览器常报私有类型，扩展名合法则放行）。"""
    ext = _validate_ext(filename)
    try:
        _validate_mime(content_type)
    except BusinessException:
        pass
    return ext


def _check_secrecy(att, current_user: dict) -> None:
    secrecy = getattr(att, "secrecy_level", "internal") or "internal"
    perms = current_user.get("permissions", [])
    if secrecy == "restricted" and "attachment:view_restricted" not in perms:
        raise BusinessException(message="此文件为受限密级，您没有下载权限")
    if secrecy == "confidential" and "attachment:view_confidential" not in perms:
        raise BusinessException(message="此文件为机密密级，您没有下载权限")


async def _authenticate(request: Request, token: Optional[str]) -> dict:
    """Authenticate from the Authorization header OR a ?token= query param.

    The query param is needed for file URLs used as <img>/<iframe>/<a href> where
    the browser cannot attach the Authorization header.
    """
    raw = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        raw = auth[7:]
    elif token:
        raw = token
    if not raw:
        raise BusinessException(code=UNAUTHORIZED, message="未认证")
    from app.domains.auth.jwt_handler import decode_token
    return decode_token(raw, expected_type="access")


# ---------------------------------------------------------------------------
# Upload (server-side multipart — used when backend is local storage)
# ---------------------------------------------------------------------------
@router.post("")
async def upload(
    file: UploadFile = File(...),
    biz_type: str = Form(None),
    biz_id: str = Form(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:upload")),
):
    filename = file.filename or "unknown"
    _validate_upload_type(filename, file.content_type)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise BusinessException(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    try:
        att = await service.upload_attachment(
            db, tenant_id, current_user,
            filename, file.content_type or "application/octet-stream",
            content, biz_type, biz_id,
        )
    except StorageError as e:
        raise BusinessException(message=f"文件存储失败：{e}")
    return ok({
        "id": att.id, "original_name": att.original_name,
        "content_type": att.content_type, "file_size": att.file_size,
        "created_at": att.created_at.isoformat() if att.created_at else "",
    })


# ---------------------------------------------------------------------------
# Direct upload (browser → object storage) — 直传
# ---------------------------------------------------------------------------
class PresignUploadBody(BaseModel):
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    biz_type: Optional[str] = None
    biz_id: Optional[str] = None


class RegisterBody(BaseModel):
    key: str
    original_name: str
    content_type: Optional[str] = None
    biz_type: Optional[str] = None
    biz_id: Optional[str] = None


@router.post("/presign-upload")
async def presign_upload(
    body: PresignUploadBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_permissions("attachment:upload")),
):
    """Issue a presigned PUT URL for browser-direct upload.

    Returns {"mode": "multipart"} when the active backend is local storage —
    the client should then fall back to the regular POST /api/v1/attachments.
    """
    _validate_upload_type(body.filename, body.content_type)
    if body.file_size and body.file_size > MAX_FILE_SIZE:
        raise BusinessException(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    from app.domains.admin.service import resolve_storage_backend
    backend, storage_type = await resolve_storage_backend(db, tenant_id)
    if not backend.supports_direct():
        return ok({"mode": "multipart"})

    key = build_object_key(tenant_id, body.filename)
    try:
        url = backend.presign_put(key, expires=PRESIGN_EXPIRES, content_type=body.content_type)
    except StorageError as e:
        raise BusinessException(message=f"生成上传链接失败：{e}")
    return ok({
        "mode": "direct", "storage_backend": storage_type,
        "key": key, "upload_url": url, "method": "PUT", "expires_in": PRESIGN_EXPIRES,
    })


@router.post("/register")
async def register_uploaded(
    body: RegisterBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:upload")),
):
    """Register an attachment after a successful browser-direct upload."""
    import asyncio
    _validate_ext(body.original_name)
    # The key was minted by /presign-upload with the tenant prefix — re-check it.
    if not body.key.startswith(f"{tenant_id}/"):
        raise BusinessException(message="非法的存储路径")

    from app.domains.admin.service import resolve_storage_backend
    backend, storage_type = await resolve_storage_backend(db, tenant_id)
    if not backend.supports_direct():
        raise BusinessException(message="当前存储后端不支持直传")

    # Trust the object store, not the client, for size/content-type.
    try:
        st = await asyncio.to_thread(backend.stat, body.key)
    except Exception:
        st = None
    if not st:
        raise BusinessException(message="文件未上传成功，请重试")
    if st["size"] > MAX_FILE_SIZE:
        try:
            await backend.delete(body.key)
        except Exception:
            pass
        raise BusinessException(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

    att = await service.register_uploaded(
        db, tenant_id, current_user, body.key, body.original_name,
        body.content_type or st.get("content_type"), int(st["size"]),
        storage_type, body.biz_type, body.biz_id,
    )
    return ok({
        "id": att.id, "original_name": att.original_name,
        "content_type": att.content_type, "file_size": att.file_size,
        "created_at": att.created_at.isoformat() if att.created_at else "",
    })


# ---------------------------------------------------------------------------
# Listing / link
# ---------------------------------------------------------------------------
class LinkAttachmentsBody(BaseModel):
    attachment_ids: list[str]
    biz_type: str
    biz_id: str


@router.post("/link")
async def link_attachments(
    body: LinkAttachmentsBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permissions("attachment:upload")),
):
    """创建页可先用 FileField 直传（无 biz），落库后再挂到业务单据。"""
    n = await service.link_attachments(
        db, tenant_id, current_user,
        body.attachment_ids, body.biz_type, body.biz_id,
    )
    return ok({"linked": n})


@router.get("/by_biz")
async def list_by_biz(
    biz_type: str,
    biz_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    via_wf = await _require_attachment_download_or_wf(
        db, tenant_id, current_user, biz_type=biz_type, biz_id=biz_id,
    )
    items = await service.list_by_biz(
        db, tenant_id, biz_type, biz_id, None if via_wf else current_user,
    )
    return ok([{
        "id": a.id, "original_name": a.original_name,
        "content_type": a.content_type, "file_size": a.file_size,
        "uploader_name": a.uploader_name,
        "secrecy_level": getattr(a, "secrecy_level", "internal") or "internal",
        "storage_backend": getattr(a, "storage_backend", "local") or "local",
        "created_at": a.created_at.isoformat() if a.created_at else "",
    } for a in items])


@router.get("/batch")
async def batch_get_attachments(
    ids: str = Query(..., description="逗号分隔的附件 id，最多 50 个"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """按 id 批量取附件元数据（低代码字段只读列表补全大小/上传人/时间）。"""
    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()][:50]
    out = []
    for aid in id_list:
        try:
            via_wf = await _require_attachment_download_or_wf(
                db, tenant_id, current_user, attachment_id=aid,
            )
            att = await service.get_attachment(
                db, tenant_id, aid, None if via_wf else current_user,
            )
        except BusinessException:
            continue
        out.append({
            "id": att.id,
            "original_name": att.original_name,
            "content_type": att.content_type,
            "file_size": att.file_size,
            "uploader_name": att.uploader_name,
            "created_at": att.created_at.isoformat() if att.created_at else "",
        })
    return ok(out)


# blob: URL 在 Chrome PDF 工具栏会显示 UUID；改走带真实文件名的临时预览地址
_PRINT_PREVIEW_TTL = 15 * 60
_PRINT_PREVIEW_MAX = 24
_PRINT_PREVIEW_MAX_BYTES = 20 * 1024 * 1024
_print_previews: dict[str, tuple[bytes, str, float]] = {}


def _safe_preview_filename(name: str | None) -> str:
    raw = (name or "document.pdf").replace("\\", "_").replace("/", "_")
    raw = "".join(c for c in raw if c.isprintable() and c not in '<>:"|?*#%')
    raw = raw.strip() or "document.pdf"
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    return raw


def _purge_print_previews() -> None:
    now = time.time()
    for key in [k for k, item in _print_previews.items() if item[2] < now]:
        _print_previews.pop(key, None)
    while len(_print_previews) > _PRINT_PREVIEW_MAX:
        oldest = min(_print_previews, key=lambda k: _print_previews[k][2])
        _print_previews.pop(oldest, None)


@router.post("/print-previews")
async def create_print_preview(
    file: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
):
    """登录用户把打印 PDF 暂存几分钟，供 iframe 用带文件名的 URL 打开。"""
    data = await file.read()
    if len(data) > _PRINT_PREVIEW_MAX_BYTES:
        raise BusinessException(message="预览文件过大")
    if not data:
        raise BusinessException(message="预览文件为空")
    filename = _safe_preview_filename(file.filename)
    token = uuid.uuid4().hex
    _purge_print_previews()
    _print_previews[token] = (data, filename, time.time() + _PRINT_PREVIEW_TTL)
    quoted = urllib.parse.quote(filename)
    return ok({
        "token": token,
        "url": f"/api/v1/attachments/print-previews/{token}/{quoted}",
    })


@router.get("/print-previews/{token}/{filename:path}")
async def get_print_preview(token: str, filename: str):
    """无鉴权：token 足够随机；iframe 无法带 Authorization。"""
    _purge_print_previews()
    item = _print_previews.get(token)
    if not item:
        raise BusinessException(code=NOT_FOUND, message="预览已过期，请重新打印")
    data, stored_name, _exp = item
    name = _safe_preview_filename(filename) or stored_name
    quoted = urllib.parse.quote(name)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quoted}",
            "Cache-Control": "no-store",
        },
    )


# ---------------------------------------------------------------------------
# Download / preview
# ---------------------------------------------------------------------------
@router.get("/{attachment_id}/url")
async def get_download_url(
    attachment_id: str,
    request: Request,
    download: int = Query(0, description="1=下载(attachment) 0=预览(inline)"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return a directly-usable URL for preview/download.

    Object storage → a presigned URL (browser fetches OSS/MinIO directly).
    Local storage  → a short token-bearing URL back to this API.
    """
    via_wf = await _require_attachment_download_or_wf(
        db, tenant_id, current_user, attachment_id=attachment_id,
    )
    att = await service.get_attachment(
        db, tenant_id, attachment_id, None if via_wf else current_user,
    )
    _check_secrecy(att, current_user)
    from app.domains.lowcode.field_permission import assert_form_field_attachment_download
    await assert_form_field_attachment_download(db, tenant_id, attachment_id, current_user)
    storage_type = att.storage_backend or "local"
    inline = not download

    if storage_type != "local":
        from app.domains.admin.service import resolve_storage_backend
        try:
            backend, _ = await resolve_storage_backend(db, tenant_id, storage_type)
            url = backend.presign_get(att.stored_path, expires=PRESIGN_EXPIRES, filename=att.original_name, inline=inline)
        except StorageError as e:
            raise BusinessException(message=f"生成链接失败：{e}")
        if url:
            return ok({"url": url, "direct": True, "expires_in": PRESIGN_EXPIRES})

    # Local (or presign unsupported): self URL carrying the caller's token.
    raw = request.headers.get("Authorization", "")
    raw = raw[7:] if raw.startswith("Bearer ") else ""
    inline_flag = 1 if inline else 0
    url = (
        f"/api/v1/attachments/{attachment_id}/download"
        f"?inline={inline_flag}&token={urllib.parse.quote(raw)}"
    )
    return ok({"url": url, "direct": False, "expires_in": 0})


@router.get("/{attachment_id}/download")
async def download(
    attachment_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    inline: int = Query(0),
    proxy: int = Query(0, description="1=经本服务转发（绕过对象存储 CORS，供页内 Office 预览）"),
    db: AsyncSession = Depends(get_db),
):
    current_user = await _authenticate(request, token)
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise BusinessException(code=UNAUTHORIZED, message="租户信息缺失")
    via_wf = await _require_attachment_download_or_wf(
        db, tenant_id, current_user, attachment_id=attachment_id,
    )

    att = await service.get_attachment(
        db, tenant_id, attachment_id, None if via_wf else current_user,
    )
    _check_secrecy(att, current_user)
    from app.domains.lowcode.field_permission import assert_form_field_attachment_download
    await assert_form_field_attachment_download(db, tenant_id, attachment_id, current_user)

    storage_type = att.storage_backend or "local"
    media_type = att.content_type or "application/octet-stream"
    disposition = "inline" if inline else "attachment"

    if storage_type == "local":
        full_path = get_full_path(att.stored_path)
        if not os.path.exists(full_path):
            raise BusinessException(code=NOT_FOUND, message="文件不存在")
        return FileResponse(
            path=full_path, filename=att.original_name,
            media_type=media_type, content_disposition_type=disposition,
        )

    from app.domains.admin.service import resolve_storage_backend
    from app.domains.attachment.storage import _content_disposition
    try:
        backend, _ = await resolve_storage_backend(db, tenant_id, storage_type)
        # 页内 Word/Excel 等需用 fetch 读 Blob；302 到 OSS 会受 CORS 限制，故可选本服务转发。
        if proxy:
            content = await backend.read(att.stored_path)
            return Response(
                content=content,
                media_type=media_type,
                headers={
                    "Content-Disposition": _content_disposition(
                        att.original_name or "file", bool(inline),
                    ),
                },
            )
        url = backend.presign_get(
            att.stored_path, expires=PRESIGN_EXPIRES,
            filename=att.original_name, inline=bool(inline),
        )
    except StorageError:
        raise BusinessException(code=NOT_FOUND, message="文件不存在")
    if not url:
        raise BusinessException(message="文件下载失败，请检查存储配置")
    return RedirectResponse(url)


async def _oss_creds_for_imm(db: AsyncSession, tenant_id: str) -> dict | None:
    """取出租户 OSS 明文凭证，供 IMM WebOffice 签发。"""
    from sqlalchemy import select
    from app.common.crypto import decrypt_config_json
    from app.domains.admin.models import TenantStorageConfig

    row = (await db.execute(
        select(TenantStorageConfig).where(TenantStorageConfig.tenant_id == tenant_id)
    )).scalar_one_or_none()
    cfg = decrypt_config_json(((row.config_json if row else None) or {}).get("oss")) or {}
    ak = (cfg.get("access_key") or "").strip()
    sk = (cfg.get("secret_key") or "").strip()
    bucket = (cfg.get("bucket") or "").strip()
    if not (ak and sk and bucket):
        return None
    return {
        "access_key": ak,
        "secret_key": sk,
        "bucket": bucket,
        "endpoint": (cfg.get("endpoint") or "").strip(),
    }


class WebOfficeRefreshBody(BaseModel):
    access_token: str
    refresh_token: str


@router.post("/weboffice/refresh")
async def refresh_weboffice_token(
    body: WebOfficeRefreshBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """续期 IMM WebOffice 凭证（AccessToken 约 30 分钟）。"""
    from app.domains.admin.service import get_imm_config
    from app.domains.attachment import weboffice_service as wos

    imm = await get_imm_config(db, tenant_id)
    if not wos.is_imm_configured(imm):
        raise BusinessException(message="未配置在线文档预览服务（IMM）")
    creds = await _oss_creds_for_imm(db, tenant_id)
    if not creds:
        raise BusinessException(message="未配置阿里云 OSS，无法续期预览凭证")
    data = await asyncio.to_thread(
        wos.refresh,
        imm=imm,
        access_key=creds["access_key"],
        secret_key=creds["secret_key"],
        endpoint=creds["endpoint"],
        access_token=body.access_token,
        refresh_token=body.refresh_token,
    )
    return ok(data)


@router.get("/{attachment_id}/weboffice")
async def get_attachment_weboffice(
    attachment_id: str,
    no_download: int = Query(0, description="1=关闭复制/导出/打印"),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """签发 IMM WebOffice 预览凭证（.doc / PPT 等）。

    未开通 IMM 或文件不在 OSS 时返回 enabled=false，前端回退本地预览/下载。
    """
    from app.domains.admin.service import get_imm_config
    from app.domains.attachment import weboffice_service as wos

    via_wf = await _require_attachment_download_or_wf(
        db, tenant_id, current_user, attachment_id=attachment_id,
    )
    att = await service.get_attachment(
        db, tenant_id, attachment_id, None if via_wf else current_user,
    )
    _check_secrecy(att, current_user)
    from app.domains.lowcode.field_permission import assert_form_field_attachment_download
    await assert_form_field_attachment_download(db, tenant_id, attachment_id, current_user)

    name = att.original_name or ""
    if not wos.needs_weboffice(name):
        return ok({"enabled": False, "reason": "unsupported"})

    imm = await get_imm_config(db, tenant_id)
    if not wos.is_imm_configured(imm):
        return ok({"enabled": False, "reason": "not_configured"})
    if (att.storage_backend or "local") != "oss":
        return ok({"enabled": False, "reason": "not_oss"})

    creds = await _oss_creds_for_imm(db, tenant_id)
    if not creds:
        return ok({"enabled": False, "reason": "not_configured"})

    data = await asyncio.to_thread(
        wos.generate,
        imm=imm,
        access_key=creds["access_key"],
        secret_key=creds["secret_key"],
        bucket=creds["bucket"],
        endpoint=creds["endpoint"],
        storage_key=att.stored_path,
        filename=name,
        user_id=str(current_user.get("sub") or ""),
        user_name=str(current_user.get("real_name") or current_user.get("username") or ""),
        allow_download=not bool(no_download),
    )
    return ok({"enabled": True, **data})


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permissions("attachment:upload")),
):
    await service.delete_attachment(db, tenant_id, attachment_id, _user)
    return ok(None)
