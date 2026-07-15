"""财务模型：账户/科目/流水"""
from ..utils import utcnow
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String

from .base import Base
from .enterprise import pk


class FinanceAccount(Base):
    """账户（资金账户 + 复式会计科目，2026-07-15 复式改造）"""
    __tablename__ = "finance_accounts"

    id = pk()
    code = Column(String(32), nullable=True, index=True)  # 科目编号（1001/1002/4001...）
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)  # cash/bank/wechat/alipay（资金账户类型）
    # 复式记账 5 大类 + 余额方向（资产/支出=借，负债/权益/收入=贷）
    account_type = Column(String(10), nullable=False, default="asset")  # asset/liability/equity/revenue/expense
    balance_direction = Column(String(6), nullable=False, default="debit")  # debit/credit
    parent_id = Column(BigInteger, nullable=True, index=True)  # 母科目（树形）
    is_leaf = Column(Boolean, default=True)  # 末级科目（可记账）
    balance = Column(Numeric(14, 2), default=Decimal("0"))
    status = Column(Boolean, default=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


class FinanceCategory(Base):
    """收支科目（树形）"""
    __tablename__ = "finance_categories"

    id = pk()
    parent_id = Column(BigInteger, nullable=True, index=True)
    name = Column(String(50), nullable=False)
    type = Column(String(10), nullable=False)  # income / expense
    code = Column(String(50), nullable=True, index=True)
    sort = Column(Integer, default=0)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class FinanceTransaction(Base):
    """财务流水"""
    __tablename__ = "finance_transactions"

    id = pk()
    type = Column(String(10), nullable=False)  # income / expense
    amount = Column(Numeric(12, 2), nullable=False)
    account_id = Column(BigInteger, ForeignKey("finance_accounts.id"), nullable=False, index=True)
    category_id = Column(BigInteger, ForeignKey("finance_categories.id"), nullable=False, index=True)
    dept_id = Column(BigInteger, nullable=True, index=True)
    user_id = Column(BigInteger, nullable=True, index=True)
    transaction_date = Column(DateTime, nullable=False, default=utcnow, index=True)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class Voucher(Base):
    """记账凭证（复式，含多条分录 JournalEntry，借贷平衡）。

    2026-07-15 标准复式记账改造（替代单式 FinanceTransaction）。
    """
    __tablename__ = "finance_vouchers"

    id = pk()
    number = Column(String(32), nullable=False, index=True)  # 凭证编号（记-20260715-001）
    voucher_date = Column(DateTime, nullable=False, default=utcnow, index=True)
    summary = Column(String(200), nullable=True)
    status = Column(String(10), default="draft", nullable=False)  # draft / posted
    attachment_count = Column(Integer, default=0)
    created_by = Column(BigInteger, nullable=True, index=True)
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class JournalEntry(Base):
    """分录（凭证的借贷行，同一 voucher 的 Σdebit 必须等于 Σcredit）。"""
    __tablename__ = "finance_journal_entries"

    id = pk()
    voucher_id = Column(BigInteger, ForeignKey("finance_vouchers.id"), nullable=False, index=True)
    account_id = Column(BigInteger, ForeignKey("finance_accounts.id"), nullable=False, index=True)
    debit = Column(Numeric(14, 2), default=Decimal("0"))  # 借方金额
    credit = Column(Numeric(14, 2), default=Decimal("0"))  # 贷方金额
    summary = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)
