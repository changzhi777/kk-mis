"""财务模型：账户/科目/流水"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String

from .base import Base
from .enterprise import pk


class FinanceAccount(Base):
    """账户（现金/银行/微信…）"""
    __tablename__ = "finance_accounts"

    id = pk()
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)  # cash/bank/wechat/alipay
    balance = Column(Numeric(12, 2), default=Decimal("0"))
    status = Column(Boolean, default=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


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
    transaction_date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
