import enum
from typing import List
import sqlalchemy as sa
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import  DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Numeric, CheckConstraint, UniqueConstraint

from engine import db_engine

class Base(DeclarativeBase):
    pass

class AccountType(enum.Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CASH = "cash"
    MONEY_MARKET = "money_market"

class CategoryType(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class User(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    firstname: Mapped[str] = mapped_column(String(128), nullable=False)
    lastname: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(128), nullable=False)

    accounts: Mapped[List["Accounts"]] = relationship(
        back_populates="user", 
        cascade="all, delete-orphan"
    )
    investments: Mapped[List["InvestmentAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    savings_goals: Mapped[List["SavingsGoal"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

class Accounts(Base):
    __tablename__ = "account"

    account_id: Mapped[int] = mapped_column(primary_key=True)

    account_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )

    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00")
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id"),
        nullable=False
    )

    account_type: Mapped[AccountType] = mapped_column(
        sa.Enum(
            AccountType,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ]
        ),
        default=AccountType.CASH,
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="accounts"
    )

    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="account"
    )

    __table_args__ = (
        CheckConstraint(
            "opening_balance >= 0",
            name="check_opening_balance"
        ),
    )

class Categories(Base):
    __tablename__ = "category"

    category_id: Mapped[int] = mapped_column(primary_key=True)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        sa.Enum(
            CategoryType,
            values_callable=lambda enum_cls: [item.value for item in enum_cls]
        ),
        nullable=False
    )

    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="category"
    )

    __table_args__ = (
        UniqueConstraint(
            "category_name",
            "category_type",
            name="uq_category_name_type"
        ),
    )

class Transaction(Base):
    __tablename__ = "transaction"

    transaction_id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account.account_id"),
        nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.category_id"),
        nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(default=date.today, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    account: Mapped["Accounts"] = relationship(back_populates="transactions")
    category: Mapped["Categories"] = relationship(back_populates="transactions")

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_transaction_amount"),
        sa.Index("ix_transaction_account_date", "account_id", "transaction_date"),
        sa.Index("ix_transaction_category", "category_id"),
    )

class InvestmentVehicle(Base):
    __tablename__ = "investment_vehicle"

    vehicle_id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str]=mapped_column(String(255), nullable=True)

    investment_accounts: Mapped[List["InvestmentAccount"]] = relationship(
        back_populates="vehicle"
    )

class InvestmentAccount(Base):
    __tablename__ = "investment_account"

    investment_id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id"),
        nullable=False
    )

    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("investment_vehicle.vehicle_id"),
        nullable=False
    )

    investment_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    opened_date: Mapped[date] = mapped_column(default=date.today, nullable=False)

    user: Mapped["User"] = relationship(
        back_populates="investments"
    )

    vehicle: Mapped["InvestmentVehicle"] = relationship(
        back_populates="investment_accounts"
    )

    snapshots: Mapped[List["InvestmentSnapshot"]] = relationship(
        back_populates="investment_account",
        cascade="all, delete-orphan"
    )

    transactions: Mapped[List["InvestmentTransaction"]] = relationship(
        back_populates="investment_account",
        cascade="all, delete-orphan"
    )

class InvestmentSnapshot(Base):
    __tablename__ = "investment_snapshot"

    snapshot_id: Mapped[int] = mapped_column(primary_key=True)
    investment_id: Mapped[int] = mapped_column(
        ForeignKey("investment_account.investment_id"),
        nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(default=date.today, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=False)

    investment_account: Mapped["InvestmentAccount"] = relationship(
        back_populates="snapshots"
    )
    
    __table_args__ = (
        UniqueConstraint(
            "investment_id",
            "snapshot_date",
            name="uq_investment_snapshot_date"
        ),
        CheckConstraint("value >= 0", name="check_snapshot_value"),
    )

class InvestmentTransactionType(enum.Enum):
    CONTRIBUTION = "contribution"
    WITHDRAWAL = "withdrawal"

class InvestmentTransaction(Base):
    __tablename__ = "investment_transaction"

    transaction_id: Mapped[int] = mapped_column(primary_key=True)

    investment_id: Mapped[int] = mapped_column(
        ForeignKey("investment_account.investment_id"),
        nullable=False
    )

    transaction_type: Mapped[InvestmentTransactionType] = mapped_column(
        sa.Enum(
            InvestmentTransactionType,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ]
        ),
        nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    transaction_date: Mapped[date] = mapped_column(
        default=date.today,
        nullable=False
    )

    investment_account: Mapped["InvestmentAccount"] = relationship(
        back_populates="transactions"
    )

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="check_investment_transaction_amount"
        ),
    )    


class SavingsGoal(Base):
    __tablename__ = "savings_goal"

    goal_id: Mapped[int] = mapped_column(primary_key=True)
    goal_name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=False)
    start_date: Mapped[date] = mapped_column(default=date.today, nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)

    contributions: Mapped[List["GoalContribution"]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan"
    )
    user_id: Mapped[int] = mapped_column(
    ForeignKey("user_account.id"),
    nullable=False
    )
    user: Mapped["User"] = relationship(
    back_populates="savings_goals"
    )

    __table_args__ = (
        CheckConstraint("target_amount > 0", name="check_goal_target"),
        CheckConstraint("end_date >= start_date", name="check_goal_dates"),
    )

    

class GoalContribution(Base):
    __tablename__ = "goal_contribution"

    contribution_id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("savings_goal.goal_id"),
        nullable=False
    )
    contribution_date: Mapped[date] = mapped_column(default=date.today, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=False)
    goal: Mapped["SavingsGoal"] = relationship(back_populates="contributions")
    account_id: Mapped[int | None] = mapped_column(
    ForeignKey("account.account_id"),
    nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_contribution_amount"),
    )


Base.metadata.create_all(db_engine)
