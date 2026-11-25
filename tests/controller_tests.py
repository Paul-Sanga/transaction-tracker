from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session


import controller
from models import (
    Accounts,
    AccountType,
    Categories,
    CategoryType,
    Transaction,
)


def test_create_account(
    runner,
    db,
    authenticated_user
):
    result = runner.invoke(
        controller.account,
        [
            "create",
            "--name", "Emergency Savings",
            "--open_balance", "5000.00",
        ],
        input="savings\n",
    )

    assert result.exit_code == 0
    assert "Account created successfully" in result.output

    with Session(db) as session:
        account = session.scalar(
            select(Accounts).where(
                Accounts.account_name == "Emergency Savings"
            )
        )

        assert account is not None
        assert account.user_id == authenticated_user
        assert account.account_type == AccountType.SAVINGS
        assert account.opening_balance == 5000


def test_create_transaction(
    runner,
    db,
    authenticated_user
):
    with Session(db) as session:
        account = Accounts(
            account_name="Checking",
            opening_balance=Decimal("10000.00"),
            account_type=AccountType.CHECKING,
            user_id=authenticated_user,
        )

        category = Categories(
            category_name="Salary",
            category_type=CategoryType.INCOME,
        )

        session.add_all([account, category])
        session.commit()

        account_id = account.account_id
        category_id = category.category_id

    result = runner.invoke(
        controller.transaction,
        [
            "create",
            "--account-id", str(account_id),
            "--category-id", str(category_id),
            "--amount", "50000.00",
            "--description", "November salary",
            "--date", "2026-11-01",
        ],
    )

    assert result.exit_code == 0
    assert "Transaction recorded successfully" in result.output

    with Session(db) as session:
        transaction = session.scalar(
            select(Transaction).where(
                Transaction.description == "November salary"
            )
        )

        assert transaction is not None
        assert transaction.amount == Decimal("50000.00")
        assert transaction.account_id == account_id
        assert transaction.category_id == category_id



def test_goal_rejects_zero_target(
    runner,
    db,
    authenticated_user
):
    result = runner.invoke(
        controller.goal,
        [
            "create",
            "--name", "Emergency Fund",
            "--target", "0",
            "--end-date", "2027-12-31",
        ],
    )

    assert result.exit_code != 0
    assert "Target must be greater than zero" in result.output
