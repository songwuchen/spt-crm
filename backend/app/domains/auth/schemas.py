from typing import Optional, List
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None


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


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


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
