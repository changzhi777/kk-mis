"""企业管理模型：部门/用户/角色/权限（RBAC）"""
from ..utils import utcnow
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Table,
)

from .base import Base


def pk():
    """主键：SQLite 用 Integer（自动递增），PG 用 BigInteger"""
    return Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)


# 用户-角色 多对多
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

# 角色-权限 多对多
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Department(Base):
    """部门（树形）"""
    __tablename__ = "departments"

    id = pk()
    parent_id = Column(BigInteger, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=True, index=True)
    leader = Column(String(50), nullable=True)
    sort = Column(Integer, default=0)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id = pk()
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    dept_id = Column(BigInteger, nullable=True, index=True)
    status = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    preferences = Column(JSON, nullable=True)  # 用户偏好（dashboard 模块顺序等）
    created_at = Column(DateTime, default=utcnow)


class Role(Base):
    __tablename__ = "roles"

    id = pk()
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    sort = Column(Integer, default=0)
    status = Column(Boolean, default=True)
    # 数据权限范围：all=全部 / dept=本部门 / self=本人
    data_scope = Column(String(20), default="all")
    remark = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class Permission(Base):
    """权限（树形）：menu 菜单 / api 接口 / button 按钮"""
    __tablename__ = "permissions"

    id = pk()
    parent_id = Column(BigInteger, nullable=True, index=True)
    name = Column(String(50), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    type = Column(String(10), nullable=False)  # menu / api / button
    path = Column(String(200), nullable=True)  # 前端路由 或 后端 api
    method = Column(String(10), nullable=True)  # api 类型：GET/POST/PUT/DELETE
    icon = Column(String(50), nullable=True)
    sort = Column(Integer, default=0)
    visible = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
