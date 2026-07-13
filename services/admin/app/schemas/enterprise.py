"""企业管理 Schema：部门/用户/角色/权限"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ===== 部门 =====
class DepartmentBase(BaseModel):
    name: str = Field(..., max_length=100)
    parent_id: Optional[int] = None
    code: Optional[str] = Field(None, max_length=50)
    leader: Optional[str] = Field(None, max_length=50)
    sort: int = 0
    status: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(DepartmentBase):
    pass


class DepartmentOut(DepartmentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ===== 角色 =====
class RoleBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=50)
    sort: int = 0
    status: bool = True
    data_scope: str = "all"
    remark: Optional[str] = Field(None, max_length=200)


class RoleCreate(RoleBase):
    permission_ids: List[int] = []


class RoleUpdate(RoleBase):
    permission_ids: List[int] = []


class RoleOut(RoleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ===== 权限 =====
class PermissionOut(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    code: str
    type: str
    path: Optional[str] = None
    method: Optional[str] = None
    icon: Optional[str] = None
    sort: int
    visible: bool
    children: List["PermissionOut"] = []

    model_config = ConfigDict(from_attributes=True)


class PermissionCreate(BaseModel):
    parent_id: Optional[int] = None
    name: str = Field(..., max_length=50)
    code: str = Field(..., max_length=100)
    type: str = Field(..., pattern="^(menu|api|button)$")
    path: Optional[str] = None
    method: Optional[str] = None
    icon: Optional[str] = None
    sort: int = 0
    visible: bool = True


class PermissionUpdate(PermissionCreate):
    pass


# ===== 用户 =====
class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dept_id: Optional[int] = None
    role_ids: List[int] = []
    status: bool = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dept_id: Optional[int] = None
    role_ids: Optional[List[int]] = None
    status: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dept_id: Optional[int] = None
    status: bool
    role_ids: List[int] = []

    model_config = ConfigDict(from_attributes=True)


class UserResetPassword(BaseModel):
    password: str = Field(..., min_length=6, max_length=128)
