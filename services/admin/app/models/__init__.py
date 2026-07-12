"""SQLAlchemy 模型聚合"""
from .agent import Agent, AgentOrder, CommissionRecord, CommissionRule
from .asset import AssetCard, AssetCardBatch, AssetCardType, AssetRedemption
from .audit import AuditLog
from .oa import (
    Announcement,
    ApprovalFlow,
    ApprovalInstance,
    ApprovalRecord,
    Attendance,
    ExpenseRequest,
    LeaveRequest,
    WorkReport,
)
from .base import Base
from .enterprise import (
    Department,
    Permission,
    Role,
    User,
    role_permissions,
    user_roles,
)
from .finance import FinanceAccount, FinanceCategory, FinanceTransaction

__all__ = [
    "Base",
    "Department",
    "User",
    "Role",
    "Permission",
    "user_roles",
    "role_permissions",
    "FinanceAccount",
    "FinanceCategory",
    "FinanceTransaction",
    "AssetCardType",
    "AssetCardBatch",
    "AssetCard",
    "AssetRedemption",
    "Agent",
    "AgentOrder",
    "CommissionRule",
    "CommissionRecord",
    "AuditLog",
    "Announcement",
    "ApprovalFlow",
    "ApprovalInstance",
    "ApprovalRecord",
    "LeaveRequest",
    "ExpenseRequest",
    "WorkReport",
    "Attendance",
]
