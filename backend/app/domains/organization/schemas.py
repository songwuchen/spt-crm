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


class UserBulkRoles(BaseModel):
    user_ids: List[str]
    role_ids: List[str] = []
    mode: str = "replace"  # replace=覆盖角色 / add=追加角色


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
    # 勾选后该用户下次改密免填原密码——用于「管理员代设了一个用户并不知晓的密码」，
    # 例如钉钉同步建号时写入的租户默认密码。不勾选则清除该标记（管理员已把新密码
    # 告知本人，应当恢复常规校验）。
    require_change: bool = False


# --- Role ---
class RoleCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    data_scope: Optional[str] = None  # self / dept / all


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data_scope: Optional[str] = None  # self / dept / all


class RoleOut(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool
    data_scope: Optional[str] = None
    permissions: List[str] = []

    model_config = {"from_attributes": True}


class GrantPermissions(BaseModel):
    permission_ids: List[str]


# --- Dept -> Role auto-assignment rules ---
class DeptRoleRuleCreate(BaseModel):
    department_id: str
    role_id: str
    include_children: bool = True
    enabled: bool = True


class DeptRoleRuleUpdate(BaseModel):
    include_children: Optional[bool] = None
    enabled: Optional[bool] = None


class DeptRoleRuleOut(BaseModel):
    id: str
    department_id: str
    department_name: Optional[str] = None
    department_path: Optional[str] = None
    role_id: str
    role_code: Optional[str] = None
    role_name: Optional[str] = None
    include_children: bool
    enabled: bool

    model_config = {"from_attributes": True}
