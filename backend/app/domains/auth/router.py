from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.common.schemas import ok
from app.domains.auth.schemas import LoginRequest, TokenResponse, RefreshRequest, UserInfo, ChangePasswordRequest, UpdateProfileRequest
from app.domains.auth.service import authenticate, get_user_permissions, get_user_roles
from app.domains.auth.jwt_handler import create_access_token, create_refresh_token, decode_token

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    from app.domains.audit.service import log_action

    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )

    try:
        user = await authenticate(db, body.username, body.password)
    except Exception as e:
        # Log failed login attempt
        try:
            await log_action(
                db, tenant_id="", user_id="", user_name=body.username,
                action="login_failed", resource_type="auth", resource_id="",
                summary=f"登录失败: {body.username} from {client_ip}",
            )
        except Exception:
            pass
        raise

    permissions = await get_user_permissions(db, user.id, user.tenant_id)
    roles = await get_user_roles(db, user.id, user.tenant_id)

    payload = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "username": user.username,
        "real_name": user.real_name,
        "permissions": permissions,
        "roles": roles,
    }
    token_data = TokenResponse(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token({"sub": user.id, "tenant_id": user.tenant_id}),
    )

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

    return ok(token_data.model_dump())


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    user_id = payload["sub"]
    tenant_id = payload["tenant_id"]

    permissions = await get_user_permissions(db, user_id, tenant_id)
    roles = await get_user_roles(db, user_id, tenant_id)

    new_payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "permissions": permissions,
        "roles": roles,
    }
    token_data = TokenResponse(
        access_token=create_access_token(new_payload),
        refresh_token=create_refresh_token({"sub": user_id, "tenant_id": tenant_id}),
    )
    return ok(token_data.model_dump())


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.domains.auth.models import User
    from sqlalchemy import select

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
    from sqlalchemy import select

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
    from sqlalchemy import select
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


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import bcrypt
    from app.domains.auth.models import User
    from app.common.exceptions import BusinessException
    from sqlalchemy import select

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
    await db.commit()
    return ok(None, message="密码修改成功")
