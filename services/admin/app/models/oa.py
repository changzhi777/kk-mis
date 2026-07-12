"""OA 办公模型：公告 + 审批工作流 + 请假 + 报销 + 工作汇报 + 考勤"""
from ..utils import utcnow
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from .base import Base
from .enterprise import pk


class Announcement(Base):
    """公告/通知（scope: all 全员 / dept 指定部门）"""
    __tablename__ = "announcement"

    id = pk()
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    publisher_id = Column(BigInteger, nullable=True)
    scope = Column(String(20), default="all")  # all / dept
    dept_id = Column(BigInteger, nullable=True)
    status = Column(String(20), default="draft", nullable=False, index=True)  # draft/published/archived
    created_at = Column(DateTime, default=utcnow)
    published_at = Column(DateTime, nullable=True)


class ApprovalFlow(Base):
    """审批流程定义（nodes_config JSON 驱动流转）"""
    __tablename__ = "approval_flow"

    id = pk()
    name = Column(String(100), nullable=False)
    business_type = Column(String(20), nullable=False, index=True)  # leave / expense
    nodes_config = Column(Text, nullable=False)  # JSON: [{node, name, approver_type:leader|user, approver_id?}]
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class ApprovalInstance(Base):
    """审批实例"""
    __tablename__ = "approval_instance"

    id = pk()
    flow_id = Column(BigInteger, ForeignKey("approval_flow.id"), nullable=False, index=True)
    applicant_id = Column(BigInteger, nullable=False, index=True)
    business_type = Column(String(20), nullable=False)  # leave / expense
    business_id = Column(BigInteger, nullable=False, index=True)  # 关联 leave_request.id 等
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending/approved/rejected
    current_node = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


class ApprovalRecord(Base):
    """审批记录（每节点一条）"""
    __tablename__ = "approval_record"

    id = pk()
    instance_id = Column(BigInteger, ForeignKey("approval_instance.id"), nullable=False, index=True)
    node = Column(Integer, nullable=False)
    approver_id = Column(BigInteger, nullable=False)
    action = Column(String(20), nullable=False)  # approve/reject/delegate
    comment = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class LeaveRequest(Base):
    """请假申请"""
    __tablename__ = "leave_request"

    id = pk()
    user_id = Column(BigInteger, nullable=False, index=True)
    type = Column(String(20), nullable=False)  # personal/sick/annual
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    days = Column(Numeric(4, 1), nullable=False)
    reason = Column(String(500), nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending/approved/rejected
    instance_id = Column(BigInteger, nullable=True)  # 关联审批实例
    created_at = Column(DateTime, default=utcnow)


class ExpenseRequest(Base):
    """报销申请（走审批，同 leave）"""
    __tablename__ = "expense_request"

    id = pk()
    user_id = Column(BigInteger, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    category = Column(String(50), nullable=False)  # travel/office/entertainment/other
    expense_date = Column(DateTime, nullable=False)
    reason = Column(String(500), nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    instance_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class WorkReport(Base):
    """工作汇报（日报/周报/月报，独立模块不走审批）"""
    __tablename__ = "work_report"

    id = pk()
    user_id = Column(BigInteger, nullable=False, index=True)
    type = Column(String(20), nullable=False)  # daily/weekly/monthly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    content = Column(Text, nullable=False)  # 本期完成
    plan_next = Column(Text, nullable=True)  # 下期计划
    problems = Column(Text, nullable=True)  # 遇到的问题
    status = Column(String(20), default="submitted", nullable=False, index=True)  # submitted/read
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Attendance(Base):
    """考勤打卡（user_id + date 唯一约束，防重复打卡）"""
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )

    id = pk()
    user_id = Column(BigInteger, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    clock_in = Column(DateTime, nullable=True)
    clock_out = Column(DateTime, nullable=True)
    status = Column(String(20), default="normal", nullable=False)  # normal/late/early
    work_hours = Column(Numeric(4, 1), nullable=True)
    created_at = Column(DateTime, default=utcnow)
