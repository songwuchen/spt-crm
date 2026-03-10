from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.common.schemas import ok
from app.domains.auth.schemas import LoginRequest, TokenResponse, RefreshRequest, UserInfo, ChangePasswordRequest, UpdateProfileRequest, TotpVerifyRequest
from app.domains.auth.service import authenticate, get_user_permissions, get_user_roles
from app.domains.auth.jwt_handler import create_access_token, create_refresh_token, decode_token, generate_jti
from app.common.exceptions import BusinessException

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


def _parse_device_type(ua: str) -> str:
    ua_lower = ua.lower()
    if any(k in ua_lower for k in ("mobile", "android", "iphone", "ipad")):
        return "mobile" if "ipad" not in ua_lower else "tablet"
    return "desktop"


def _get_client_ip(request: Request) -> str:
    return request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    from app.domains.audit.service import log_action
    from app.domains.auth.models import LoginSession

    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    try:
        user = await authenticate(db, body.username, body.password)
    except Exception as e:
        try:
            await log_action(
                db, tenant_id="", user_id="", user_name=body.username,
                action="login_failed", resource_type="auth", resource_id="",
                summary=f"登录失败: {body.username} from {client_ip}",
            )
        except Exception:
            pass
        raise

    # Check 2FA if enabled
    if user.totp_enabled and user.totp_secret:
        import pyotp
        if not body.totp_code:
            return ok({"requires_totp": True}, message="请输入二步验证码")
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(body.totp_code, valid_window=1):
            raise BusinessException(code=40100, message="二步验证码错误")

    permissions = await get_user_permissions(db, user.id, user.tenant_id)
    roles = await get_user_roles(db, user.id, user.tenant_id)

    jti = generate_jti()
    payload = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "username": user.username,
        "real_name": user.real_name,
        "permissions": permissions,
        "roles": roles,
    }
    token_data = TokenResponse(
        access_token=create_access_token(payload, jti=jti),
        refresh_token=create_refresh_token({"sub": user.id, "tenant_id": user.tenant_id}, jti=jti),
    )

    # Create login session record
    from app.config import settings
    session = LoginSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_jti=jti,
        ip=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
        device_type=_parse_device_type(user_agent),
        is_active=True,
        last_active_at=datetime.now(timezone.utc),
        expired_at=datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES),
    )
    db.add(session)

    # Log successful login
    try:
        await log_action(
            db, tenant_id=user.tenant_id, user_id=user.id,
            user_name=user.real_name or user.username,
            action="login", resource_type="auth", resource_id=user.id,
            summary=f"登录成功 from {client_ip}",
        )
    except Exception:
        pass

    await db.commit()
    return ok(token_data.model_dump())


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from app.domains.auth.models import LoginSession

    payload = decode_token(body.refresh_token, expected_type="refresh")
    user_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    old_jti = payload.get("jti")

    # Check if session is still active
    if old_jti:
        session = (await db.execute(
            select(LoginSession).where(LoginSession.token_jti == old_jti, LoginSession.is_active == True)
        )).scalar_one_or_none()
        if not session:
            from app.common.exceptions import BusinessException
            raise BusinessException(code=40100, message="会话已失效，请重新登录")
        # Update last active
        session.last_active_at = datetime.now(timezone.utc)

    permissions = await get_user_permissions(db, user_id, tenant_id)
    roles = await get_user_roles(db, user_id, tenant_id)

    new_jti = old_jti or generate_jti()
    new_payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "permissions": permissions,
        "roles": roles,
    }
    token_data = TokenResponse(
        access_token=create_access_token(new_payload, jti=new_jti),
        refresh_token=create_refresh_token({"sub": user_id, "tenant_id": tenant_id}, jti=new_jti),
    )
    await db.commit()
    return ok(token_data.model_dump())


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.domains.auth.models import User

    user = (await db.execute(select(User).where(User.id == current_user["sub"]))).scalar_one_or_none()
    if not user:
        return ok(None)

    info = UserInfo(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        real_name=user.real_name,
        phone=user.phone,
        email=user.email,
        avatar=user.avatar,
        roles=current_user.get("roles", []),
        permissions=current_user.get("permissions", []),
    )
    return ok(info.model_dump())


@router.put("/profile")
async def update_profile(body: UpdateProfileRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.domains.auth.models import User

    user = (await db.execute(select(User).where(User.id == current_user["sub"]))).scalar_one_or_none()
    if not user:
        from app.common.exceptions import BusinessException
        raise BusinessException(code=404, message="用户不存在")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return ok({"real_name": user.real_name, "phone": user.phone, "email": user.email})


@router.get("/login-history")
async def login_history(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return recent login events for the current user."""
    from app.domains.audit.models import AuditLog

    user_id = current_user["sub"]
    items = (await db.execute(
        select(AuditLog).where(
            AuditLog.user_id == user_id,
            AuditLog.resource_type == "auth",
            AuditLog.action == "login",
        ).order_by(AuditLog.created_at.desc()).limit(20)
    )).scalars().all()
    return ok([{
        "id": log.id,
        "summary": log.summary,
        "ip": log.ip,
        "created_at": log.created_at.isoformat() if log.created_at else "",
    } for log in items])


@router.get("/sessions")
async def list_sessions(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List active login sessions for current user."""
    from app.domains.auth.models import LoginSession

    user_id = current_user["sub"]
    sessions = (await db.execute(
        select(LoginSession).where(
            LoginSession.user_id == user_id,
            LoginSession.is_active == True,
        ).order_by(LoginSession.last_active_at.desc())
    )).scalars().all()

    current_jti = current_user.get("jti")
    return ok([{
        "id": s.id,
        "ip": s.ip,
        "device_type": s.device_type,
        "user_agent": s.user_agent,
        "last_active_at": s.last_active_at.isoformat() if s.last_active_at else "",
        "created_at": s.created_at.isoformat() if s.created_at else "",
        "is_current": s.token_jti == current_jti if current_jti else False,
    } for s in sessions])


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Revoke a specific login session."""
    from app.domains.auth.models import LoginSession
    from app.common.exceptions import BusinessException

    session = (await db.execute(
        select(LoginSession).where(
            LoginSession.id == session_id,
            LoginSession.user_id == current_user["sub"],
        )
    )).scalar_one_or_none()
    if not session:
        raise BusinessException(code=404, message="会话不存在")

    session.is_active = False
    await db.commit()
    return ok(None, message="会话已撤销")


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Revoke all sessions except current."""
    from app.domains.auth.models import LoginSession

    current_jti = current_user.get("jti")
    stmt = (
        update(LoginSession)
        .where(
            LoginSession.user_id == current_user["sub"],
            LoginSession.is_active == True,
        )
        .values(is_active=False)
    )
    if current_jti:
        stmt = stmt.where(LoginSession.token_jti != current_jti)
    result = await db.execute(stmt)
    await db.commit()
    return ok({"revoked": result.rowcount}, message="已撤销所有其他会话")


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import bcrypt
    from app.domains.auth.models import User, LoginSession
    from app.common.exceptions import BusinessException

    user = (await db.execute(select(User).where(User.id == current_user["sub"]))).scalar_one_or_none()
    if not user:
        raise BusinessException(code=404, message="用户不存在")

    if not bcrypt.checkpw(body.old_password.encode(), user.password_hash.encode()):
        raise BusinessException(code=400, message="原密码错误")

    # Password strength check
    new_pwd = body.new_password
    if len(new_pwd) < 8:
        raise BusinessException(code=42200, message="密码长度不能少于8位")
    has_upper = any(c.isupper() for c in new_pwd)
    has_lower = any(c.islower() for c in new_pwd)
    has_digit = any(c.isdigit() for c in new_pwd)
    if not (has_upper and has_lower and has_digit):
        raise BusinessException(code=42200, message="密码必须包含大小写字母和数字")

    user.password_hash = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt()).decode()

    # Revoke all other sessions on password change
    current_jti = current_user.get("jti")
    stmt = (
        update(LoginSession)
        .where(LoginSession.user_id == user.id, LoginSession.is_active == True)
        .values(is_active=False)
    )
    if current_jti:
        stmt = stmt.where(LoginSession.token_jti != current_jti)
    await db.execute(stmt)

    await db.commit()
    return ok(None, message="密码修改成功")


@router.post("/totp/setup")
async def totp_setup(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Generate TOTP secret and QR code URI for setup."""
    import pyotp
    from app.domains.auth.models import User

    user = (await db.execute(select(User).where(User.id == current_user["sub"]))).scalar_one_or_none()
    if not user:
        raise BusinessException(code=404, message="用户不存在")

    if user.totp_enabled:
        raise BusinessException(code=400, message="二步验证已启用，请先禁用")

    secret = pyotp.random_base32()
    user.totp_secret = secret
    await db.commit()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.username, issuer_name="SPT-CRM")
    return ok({"secret": secret, "uri": uri})


@router.post("/totp/enable")
async def totp_enable(body: TotpVerifyRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Verify TOTP code and enable 2FA."""
    import pyotp
    from app.domains.auth.models import User

    user = (await db.execute(select(User).where(User.id == current_user["sub"]))).scalar_one_or_none()
    if not user or not user.totp_secret:
        raise BusinessException(code=400, message="请先调用 setup 获取密钥")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise BusinessException(code=400, message="验证码错误，请重试")

    user.totp_enabled = True
    await db.commit()
    return ok(None, message="二步验证已启用")


@router.post("/totp/disable")
async def totp_disable(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Disable 2FA (requires password confirmation)."""
    import bcrypt
    from app.domains.auth.models import User

    user = (await db.execute(select(User).where(User.id == current_user["sub"]))).scalar_one_or_none()
    if not user:
        raise BusinessException(code=404, message="用户不存在")

    if not bcrypt.checkpw(body.old_password.encode(), user.password_hash.encode()):
        raise BusinessException(code=400, message="密码错误")

    user.totp_enabled = False
    user.totp_secret = None
    await db.commit()
    return ok(None, message="二步验证已禁用")


@router.get("/totp/status")
async def totp_status(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Check if 2FA is enabled."""
    from app.domains.auth.models import User
    user = (await db.execute(select(User).where(User.id == current_user["sub"]))).scalar_one_or_none()
    return ok({"enabled": bool(user and user.totp_enabled)})
