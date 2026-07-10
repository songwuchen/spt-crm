import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError

from app.config import settings
from app.common.exceptions import BusinessException
from app.common.error_codes import TOKEN_EXPIRED, TOKEN_INVALID


def create_access_token(data: dict, jti: str | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    if jti:
        to_encode["jti"] = jti
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict, jti: str | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "refresh"})
    if jti:
        to_encode["jti"] = jti
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def generate_jti() -> str:
    return uuid.uuid4().hex


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        # jose 默认校验 exp，过期会抛此异常（JWTError 的子类）。必须先于 JWTError 捕获，
        # 否则过期被误报为 40102(无效)，前端不会触发 refresh 续期 → 到期即掉线。
        raise BusinessException(code=TOKEN_EXPIRED, message="Token 已过期")
    except JWTError:
        raise BusinessException(code=TOKEN_INVALID, message="Token 无效")

    if payload.get("type") != expected_type:
        raise BusinessException(code=TOKEN_INVALID, message="Token 类型不匹配")

    return payload
