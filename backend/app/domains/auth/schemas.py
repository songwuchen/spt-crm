from typing import Optional, List
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None
    tenant_code: Optional[str] = None  # optional; disambiguates same username across tenants


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserInfo(BaseModel):
    id: str
    tenant_id: str
    username: str
    real_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    # 前端据此隐藏「当前密码」输入框并提示用户先设置自己的密码
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    # 仅当账号处于 must_change_password 状态（系统代建、用户从未设过密码）时可省略；
    # 其余情况服务端一律要求并校验。
    old_password: Optional[str] = None
    new_password: str


class PasswordConfirmRequest(BaseModel):
    """需要用当前密码二次确认的敏感操作（如关闭二步验证）。"""
    old_password: str


class UpdateProfileRequest(BaseModel):
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class TotpVerifyRequest(BaseModel):
    code: str


class DingTalkCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
    state: Optional[str] = None


class DingTalkJsapiLoginRequest(BaseModel):
    """容器内免登：requestAuthCode 得到的临时授权码。"""
    auth_code: str
    corp_id: Optional[str] = None
