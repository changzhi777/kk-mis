"""SQLAlchemy 模型聚合"""
from .agent import (
    Agent,
    AgentOrder,
    CommissionRecord,
    CommissionRule,
    ReferralCommission,
    WithdrawalRequest,
    YearlyCommissionRecord,
    YearlyCommissionRule,
)
from .asset import AssetCard, AssetCardBatch, AssetCardType, AssetRedemption, CardTransfer
from .audit import AuditLog
from .cms import (
    Coupon,
    EndUser,
    InquiryLead,
    MediaAsset,
    Merchant,
    OrderCard,
    PaymentExceptionEvent,
    PaymentIdempotency,
    ProductOrder,
    Review,
    TourCustom,
    TourPass,
    TourProduct,
    WebhookRetry,
)
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
from .v2 import (  # V2.0 经销商域（B2B 预付激活模型，2026-07-21）
    V2DealerApplication,
    V2DealerBalance,
    V2DealerContract,
    V2DealerQualification,
    V2DealerRecharge,
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
from .finance import FinanceAccount, FinanceCategory, FinanceTransaction, JournalEntry, Voucher

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
    "JournalEntry",
    "Voucher",
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
    "MediaAsset",
    "Merchant",
    "TourProduct",
    "TourCustom",
    "TourPass",
    "InquiryLead",
    "ProductOrder",
    "Coupon",
    "Review",
    "EndUser",
    "PaymentIdempotency",
    "WebhookRetry",
    "OrderCard",
    "PaymentExceptionEvent",  # P0 Day 2.1 缺口 #4 异常事件持久化
    "ReferralCommission",  # LOW：补 __all__ 导出（原漏）
    "WithdrawalRequest",
    "CardTransfer",
    # V2.0 经销商域（B2B 预付激活模型，2026-07-21）
    "V2DealerApplication",
    "V2DealerContract",
    "V2DealerBalance",
    "V2DealerRecharge",
    "V2DealerQualification",
]
