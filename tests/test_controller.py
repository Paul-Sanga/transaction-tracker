from sqlalchemy import select
from sqlalchemy.orm import Session

import controller
from models import Accounts, AccountType


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
