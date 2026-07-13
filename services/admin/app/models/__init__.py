"""SQLAlchemy 模型聚合"""
from .agent import (
    Agent,
    AgentOrder,
    CommissionRecord,
    CommissionRule,
    YearlyCommissionRecord,
    YearlyCommissionRule,
)
from .asset import AssetCard, AssetCardBatch, AssetCardType, AssetRedemption, CardTransfer
from .audit import AuditLog
from .member import MemberLevel, MemberStat, PointsLog
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
from .social import SocialAccount
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
    "YearlyCommissionRule",
    "YearlyCommissionRecord",
    "AuditLog",
    "MemberLevel",
    "MemberStat",
    "PointsLog",
    "Announcement",
    "ApprovalFlow",
    "ApprovalInstance",
    "ApprovalRecord",
    "LeaveRequest",
    "ExpenseRequest",
    "WorkReport",
    "Attendance",
    "SocialAccount",
]
