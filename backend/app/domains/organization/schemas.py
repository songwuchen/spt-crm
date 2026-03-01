from typing import Optional, List
from pydantic import BaseModel


# --- Department ---
class DepartmentCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None
    sort_order: int = 0
    leader_id: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None
    leader_id: Optional[str] = None


class DepartmentOut(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None
    path: str
    sort_order: int
    leader_id: Optional[str] = None
    children: List["DepartmentOut"] = []

    model_config = {"from_attributes": True}


# --- User (admin) ---
class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role_ids: List[str] = []
    department_ids: List[str] = []


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[str]] = None
    department_ids: Optional[List[str]] = None


class UserOut(BaseModel):
    id: str
    username: str
    real_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool
    roles: List[str] = []
    departments: List[str] = []

    model_config = {"from_attributes": True}


class ResetPassword(BaseModel):
    new_password: str


# --- Role ---
class RoleCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class RoleOut(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool
    permissions: List[str] = []

    model_config = {"from_attributes": True}


class GrantPermissions(BaseModel):
    permission_ids: List[str]
