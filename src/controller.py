import click
from rich import print
from pathlib import Path
from rich.table import Table
from sqlalchemy import select
from rich.console import Console
from sqlalchemy.orm import Session
from decimal import Decimal, InvalidOperation


from engine import db_engine
from validator import register_validation, login_validation
from token_util import generate_token, get_payload, auth_file
from models import User, AccountType, Accounts, CategoryType, Categories, Transaction, InvestmentAccount, InvestmentSnapshot, InvestmentTransaction, InvestmentTransactionType, InvestmentVehicle, SavingsGoal, GoalContribution

console = Console()

def current_user_id():
    try:
        user_id, _ = get_payload()
        return user_id
    except Exception:
        raise click.ClickException("You must be logged in to perform this action.")

def money(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise click.BadParameter("Enter a valid monetary amount.")

    if not amount.is_finite():
        raise click.BadParemeter("Enter a valid monetary amount")

    return amount

def confirm_delete():
    return click.confirm("Are you sure you want to delete this record?")

def success(message):
    print(f"[bold green]{message}[/bold green]")


def error(message):
    print(f"[bold red]{message}[/bold red]")

@click.group()
def auth():
    pass

@auth.command()
@click.option("--firstname", "-f", required=True)
@click.option("--lastname", "-l", required=True)
@click.option("--email", "-e", required=True)
def register(firstname: str, lastname: str, email: str| None) -> None:
    password = click.prompt(
        "Enter password",
        hide_input=True,
        confirmation_prompt=True
    )
    firstname_v, lastname_v, email_v, hashed_v = register_validation(firstname, lastname, email, password)
    with Session(db_engine) as session:
        new_user = User(
            firstname = firstname_v,
            lastname = lastname_v,
            email = email_v,
            password = hashed_v
        )
        session.add(new_user)
        session.commit()    
        session.refresh(new_user)
    print("[bold green]Registration successful![/bold green]")

@auth.command()
@click.option("--email", "-e", required=True)
def login(email: str | None) -> None:
    password = click.prompt(
        "Enter password",
        hide_input=True
    )
    user_rec = login_validation(email, password)
    generate_token(user_rec.id, user_rec.email)
    print(f"[bold green]Login succesful[/bold green]")

@auth.command()
def logout():
    try:
        file_path = Path(auth_file)
        _, email = get_payload()
        print(f"[bold green]{email} logged out![/bold green]")
        file_path.unlink(missing_ok=True)
    except FileExistsError as e:
        print("[bold red]Cannot logout user if they weren't logged in![/bold red]")

@click.group()
def account():
    pass

@account.command()
@click.option("--name", "-n", required=True)
@click.option("--open_balance", "-o", default="0.00")
def create(name: str, open_balance: str | None) -> None:
    try:
        user_id = current_user_id()
        account_type=click.prompt(
            "Select account type",
            type=click.Choice(
                [item.value for item in AccountType],
                case_sensitive=False
            )
        )
        with Session(db_engine) as session:
            new_account = Accounts(
                account_name = name,
                opening_balance = money(open_balance),
                user_id = user_id,
                account_type = AccountType(account_type.lower())
            )
            session.add(new_account)
            session.commit()
            session.refresh(new_account)
        print(f"[italic green]Account created successfully![/italic green]")
    except FileExistsError as e:
        print(f"[bold red]{e}[/bold red]")

@account.command()
def list_accounts():
    user_id = current_user_id()

    with Session(db_engine) as session:
        accounts = session.scalars(
            select(Accounts).where(Accounts.user_id == user_id)
        ).all()

        table = Table(title="My Personal Accounts")

        table.add_column("ID", justify="right")
        table.add_column("Account Name")
        table.add_column("Account Type")
        table.add_column("Currency")
        table.add_column("Opening Balance", justify="right")

        for item in accounts:
            table.add_row(
                str(item.account_id),
                item.account_name,
                item.account_type.value,
                item.currency,
                f"{item.opening_balance:,.2f}"
            )

        console.print(table)

@account.command()
@click.option("--account-id", "-i", type=int, required=True)
@click.option("--name", "-n")
@click.option("--balance", "-b")
@click.option("--account-type", "-t")
@click.option("--currency", "-c")
def update(account_id, name, balance, account_type, currency):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(Accounts).where(
                Accounts.account_id == account_id,
                Accounts.user_id == user_id
            )
        )

        if not item:
            error("Account not found.")
            return

        if name is not None:
            item.account_name = name

        if balance is not None:
            new_balance = money(balance)
            if new_balance < 0:
                raise click.BadParameter("Balance cannot be negative.")
            item.opening_balance = new_balance

        if account_type is not None:
            item.account_type = AccountType(account_type.lower())

        if currency is not None:
            if len(currency) != 3:
                raise click.BadParameter("Currency must be a 3-character code.")
            item.currency = currency.upper()

        session.commit()
    success("Account updated successfully!")

@account.command()
@click.option("--account-id", "-i", type=int, required=True)
def delete(account_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(Accounts).where(
                Accounts.account_id == account_id,
                Accounts.user_id == user_id
            )
        )

        if not item:
            error("Account not found.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Account deleted successfully!")

@click.group()
def category():
    pass

@category.command()
@click.option("--name", "-n", required=True)
@click.option("--type", "category_type", required=True,
              type=click.Choice(["income", "expense"]))
def create(name, category_type):
    with Session(db_engine) as session:
        item = Categories(
            category_name=name,
            category_type=CategoryType(category_type)
        )

        session.add(item)

        try:
            session.commit()
            success("Category created successfully!")
        except Exception:
            session.rollback()
            error("Category already exists or could not be created.")

@category.command()
def list_categories():
    with Session(db_engine) as session:
        categories = session.scalars(
            select(Categories).order_by(Categories.category_type)
        ).all()

        table = Table(title="Transaction Categories")

        table.add_column("ID")
        table.add_column("Category")
        table.add_column("Type")

        for item in categories:
            table.add_row(
                str(item.category_id),
                item.category_name,
                item.category_type.value
            )

        console.print(table)

@category.command()
@click.option("--category-id", "-i", type=int, required=True)
@click.option("--name", "-n")
@click.option("--type", "category_type",
              type=click.Choice(["income", "expense"]))
def update(category_id, name, category_type):
    with Session(db_engine) as session:
        item = session.get(Categories, category_id)

        if not item:
            error("Category not found.")
            return

        if name is not None:
            item.category_name = name

        if category_type is not None:
            item.category_type = CategoryType(category_type)

        try:
            session.commit()
            success("Category updated successfully!")
        except Exception:
            session.rollback()
            error("Unable to update category. Check for duplicate categories.")

@category.command()
@click.option("--category-id", "-i", type=int, required=True)
def delete(category_id):
    with Session(db_engine) as session:
        item = session.get(Categories, category_id)

        if not item:
            error("Category not found.")
            return

        if not confirm_delete():
            return

        if item.transactions:
            error("Cannot delete a category that has transactions.")
            return

        session.delete(item)
        session.commit()

    success("Category deleted successfully!")

@click.group()
def transaction():
    pass

@transaction.command()
@click.option("--account-id", "-a", type=int, required=True)
@click.option("--category-id", "-c", type=int, required=True)
@click.option("--amount", "-m", required=True)
@click.option("--description", "-d", required=True)
@click.option("--date", "transaction_date", default=None)
def create(account_id, category_id, amount, description, transaction_date):
    from datetime import date

    user_id = current_user_id()

    with Session(db_engine) as session:
        account_item = session.scalar(
            select(Accounts).where(
                Accounts.account_id == account_id,
                Accounts.user_id == user_id
            )
        )

        category_item = session.get(Categories, category_id)

        if not account_item:
            error("Account not found.")
            return

        if not category_item:
            error("Category not found.")
            return

        item = Transaction(
            account_id=account_id,
            category_id=category_id,
            amount=money(amount),
            description=description,
            transaction_date=(
                date.fromisoformat(transaction_date)
                if transaction_date else date.today()
            )
        )

        session.add(item)
        session.commit()

    success("Transaction recorded successfully!")

@transaction.command()
def list_transactions():
    user_id = current_user_id()

    with Session(db_engine) as session:
        records = session.scalars(
            select(Transaction)
            .join(Accounts)
            .where(Accounts.user_id == user_id)
            .order_by(Transaction.transaction_date.desc())
        ).all()

        table = Table(title="My Transactions")

        table.add_column("ID")
        table.add_column("Date")
        table.add_column("Account")
        table.add_column("Category")
        table.add_column("Description")
        table.add_column("Amount", justify="right")

        for item in records:
            table.add_row(
                str(item.transaction_id),
                str(item.transaction_date),
                item.account.account_name,
                item.category.category_name,
                item.description,
                f"{item.amount:,.2f}"
            )

        console.print(table)

@transaction.command()
@click.option("--transaction-id", "-i", type=int, required=True)
@click.option("--account-id", "-a", type=int)
@click.option("--category-id", "-c", type=int)
@click.option("--amount", "-m")
@click.option("--description", "-d")
@click.option("--date", "transaction_date")
def update(transaction_id, account_id, category_id,
           amount, description, transaction_date):
    from datetime import date

    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(Transaction)
            .join(Accounts)
            .where(
                Transaction.transaction_id == transaction_id,
                Accounts.user_id == user_id
            )
        )

        if not item:
            error("Transaction not found.")
            return

        if account_id is not None:
            account_item = session.scalar(
                select(Accounts).where(
                    Accounts.account_id == account_id,
                    Accounts.user_id == user_id
                )
            )
            if not account_item:
                error("Account not found.")
                return
            item.account_id = account_id

        if category_id is not None:
            if not session.get(Categories, category_id):
                error("Category not found.")
                return
            item.category_id = category_id

        if amount is not None:
            item.amount = money(amount)

        if description is not None:
            item.description = description

        if transaction_date is not None:
            item.transaction_date = date.fromisoformat(transaction_date)

        session.commit()

    success("Transaction updated successfully!")

@transaction.command()
@click.option("--transaction-id", "-i", type=int, required=True)
def delete(transaction_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(Transaction)
            .join(Accounts)
            .where(
                Transaction.transaction_id == transaction_id,
                Accounts.user_id == user_id
            )
        )

        if not item:
            error("Transaction not found.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Transaction deleted successfully!")

@click.group()
def transaction_summary():
    """View income and expense summaries."""
    pass


@transaction.command()
@click.option("--start-date", type=click.DateTime(
    formats=["%Y-%m-%d"]
))
@click.option("--end-date", type=click.DateTime(
    formats=["%Y-%m-%d"]
))
def summary(start_date, end_date):
    user_id = current_user_id()

    start = start_date.date() if start_date else None
    end = end_date.date() if end_date else None

    if start and end and start > end:
        raise click.BadParameter("Start date cannot be after end date.")

    with Session(db_engine) as session:
        stmt = (
            select(Transaction)
            .join(Accounts)
            .join(Categories)
            .where(Accounts.user_id == user_id)
        )

        if start:
            stmt = stmt.where(Transaction.transaction_date >= start)

        if end:
            stmt = stmt.where(Transaction.transaction_date <= end)

        records = session.scalars(stmt).all()

        income = sum(
            (item.amount for item in records
             if item.category.category_type == CategoryType.INCOME),
            Decimal("0.00")
        )

        expenses = sum(
            (item.amount for item in records
             if item.category.category_type == CategoryType.EXPENSE),
            Decimal("0.00")
        )

        net_cash_flow = income - expenses

        table = Table(title="Transaction Summary")

        table.add_column("Metric")
        table.add_column("Amount", justify="right")

        table.add_row("Total Income", f"{income:,.2f}")
        table.add_row("Total Expenses", f"{expenses:,.2f}")
        table.add_row("Net Cash Flow", f"{net_cash_flow:,.2f}")

        console.print(table)

        print(
            f"\n[dim]Period: {start or 'All time'} "
            f"to {end or 'All time'}[/dim]"
        )

@click.group()
def vehicle():
    """Manage available investment vehicles."""
    pass


@vehicle.command()
@click.option("--name", "-n", required=True)
@click.option("--description", "-d", required=False, default="")
def create(name, description):
    with Session(db_engine) as session:
        item = InvestmentVehicle(
            vehicle_name=name,
            description=description
        )

        session.add(item)

        try:
            session.commit()
            success("Investment vehicle created successfully!")
        except Exception:
            session.rollback()
            error("Investment vehicle already exists or could not be created.")


@vehicle.command()
def list_vehicles():
    with Session(db_engine) as session:
        records = session.scalars(
            select(InvestmentVehicle)
        ).all()

        table = Table(title="Investment Vehicles")
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Description")

        for item in records:
            table.add_row(
                str(item.vehicle_id),
                item.vehicle_name,
                item.description or ""
            )

        console.print(table)


@vehicle.command()
@click.option("--vehicle-id", "-i", type=int, required=True)
@click.option("--name", "-n")
@click.option("--description", "-d")
def update(vehicle_id, name, description):
    with Session(db_engine) as session:
        item = session.get(InvestmentVehicle, vehicle_id)

        if not item:
            error("Investment vehicle not found.")
            return

        if name is not None:
            item.vehicle_name = name

        if description is not None:
            item.description = description

        try:
            session.commit()
            success("Investment vehicle updated!")
        except Exception:
            session.rollback()
            error("Unable to update investment vehicle.")


@vehicle.command()
@click.option("--vehicle-id", "-i", type=int, required=True)
def delete(vehicle_id):
    with Session(db_engine) as session:
        item = session.get(InvestmentVehicle, vehicle_id)

        if not item:
            error("Investment vehicle not found.")
            return

        if item.investment_accounts:
            error("Cannot delete a vehicle currently used by investments.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Investment vehicle deleted!")



@click.group()
def investment():
    pass


@investment.command()
@click.option("--vehicle-id", "-v", type=int, required=True)
@click.option("--name", "-n", required=True)
@click.option("--provider", "-p", required=True)
def create(vehicle_id, name, provider):
    from datetime import date

    user_id = current_user_id()

    with Session(db_engine) as session:
        if not session.get(InvestmentVehicle, vehicle_id):
            error("Investment vehicle not found.")
            return

        item = InvestmentAccount(
            user_id=user_id,
            vehicle_id=vehicle_id,
            investment_name=name,
            provider=provider,
            opened_date=date.today()
        )

        session.add(item)
        session.commit()

    success("Investment account created!")


@investment.command()
def list_investments():
    user_id = current_user_id()

    with Session(db_engine) as session:
        records = session.scalars(
            select(InvestmentAccount).where(
                InvestmentAccount.user_id == user_id
            )
        ).all()

        table = Table(title="My Investments")
        table.add_column("ID")
        table.add_column("Investment")
        table.add_column("Vehicle")
        table.add_column("Provider")
        table.add_column("Opened")

        for item in records:
            table.add_row(
                str(item.investment_id),
                item.investment_name,
                item.vehicle.vehicle_name,
                item.provider,
                str(item.opened_date)
            )

        console.print(table)


@investment.command()
@click.option("--investment-id", "-i", type=int, required=True)
@click.option("--name", "-n")
@click.option("--provider", "-p")
@click.option("--vehicle-id", "-v", type=int)
def update(investment_id, name, provider, vehicle_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(InvestmentAccount).where(
                InvestmentAccount.investment_id == investment_id,
                InvestmentAccount.user_id == user_id
            )
        )

        if not item:
            error("Investment account not found.")
            return

        if name is not None:
            item.investment_name = name

        if provider is not None:
            item.provider = provider

        if vehicle_id is not None:
            if not session.get(InvestmentVehicle, vehicle_id):
                error("Investment vehicle not found.")
                return
            item.vehicle_id = vehicle_id

        session.commit()

    success("Investment account updated!")


@investment.command()
@click.option("--investment-id", "-i", type=int, required=True)
def delete(investment_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(InvestmentAccount).where(
                InvestmentAccount.investment_id == investment_id,
                InvestmentAccount.user_id == user_id
            )
        )

        if not item:
            error("Investment account not found.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Investment account and its related records deleted!")

@investment.command()
def performance():
    user_id = current_user_id()

    with Session(db_engine) as session:
        investments = session.scalars(
            select(InvestmentAccount).where(
                InvestmentAccount.user_id == user_id
            )
        ).all()

        table = Table(title="Investment Performance")

        table.add_column("Investment")
        table.add_column("Provider")
        table.add_column("Contributions", justify="right")
        table.add_column("Withdrawals", justify="right")
        table.add_column("Net Invested", justify="right")
        table.add_column("Current Value", justify="right")
        table.add_column("Gain/Loss", justify="right")
        table.add_column("Return %", justify="right")

        total_contributions = Decimal("0.00")
        total_withdrawals = Decimal("0.00")
        total_value = Decimal("0.00")
        total_net_invested = Decimal("0.00")

        for investment in investments:

            transactions = session.scalars(
                select(InvestmentTransaction).where(
                    InvestmentTransaction.investment_id
                    == investment.investment_id
                )
            ).all()

            contributions = sum(
                (
                    item.amount for item in transactions
                    if item.transaction_type
                    == InvestmentTransactionType.CONTRIBUTION
                ),
                Decimal("0.00")
            )

            withdrawals = sum(
                (
                    item.amount for item in transactions
                    if item.transaction_type
                    == InvestmentTransactionType.WITHDRAWAL
                ),
                Decimal("0.00")
            )

            net_invested = contributions - withdrawals

            latest_snapshot = session.scalar(
                select(InvestmentSnapshot)
                .where(
                    InvestmentSnapshot.investment_id
                    == investment.investment_id
                )
                .order_by(InvestmentSnapshot.snapshot_date.desc())
                .limit(1)
            )

            current_value = (
                latest_snapshot.value
                if latest_snapshot
                else None
            )

            gain_loss = (
                current_value - net_invested
                if current_value is not None
                else None
            )

            return_percentage = (
                (gain_loss / net_invested) * 100
                if gain_loss is not None and net_invested > 0
                else None
            )

            table.add_row(
                investment.investment_name,
                investment.provider,
                f"{contributions:,.2f}",
                f"{withdrawals:,.2f}",
                f"{net_invested:,.2f}",
                f"{current_value:,.2f}" if current_value is not None else "N/A",
                f"{gain_loss:,.2f}" if gain_loss is not None else "N/A",
                f"{return_percentage:.2f}%" if return_percentage is not None else "N/A"
            )

            total_contributions += contributions
            total_withdrawals += withdrawals
            total_net_invested += net_invested

            if current_value is not None:
                total_value += current_value

        console.print(table)

        total_gain = total_value - total_net_invested

        total_return = (
            (total_gain / total_net_invested) * 100
            if total_net_invested > 0
            else None
        )

        summary = Table(title="Portfolio Summary")

        summary.add_column("Metric")
        summary.add_column("Amount", justify="right")

        summary.add_row(
            "Total Contributions",
            f"{total_contributions:,.2f}"
        )
        summary.add_row(
            "Total Withdrawals",
            f"{total_withdrawals:,.2f}"
        )
        summary.add_row(
            "Net Invested",
            f"{total_net_invested:,.2f}"
        )
        summary.add_row(
            "Latest Valuations (available)",
            f"{total_value:,.2f}"
        )
        summary.add_row(
            "Gain/Loss (partial if snapshots missing)",
            f"{total_gain:,.2f}"
        )
        summary.add_row(
            "Return (partial if snapshots missing)",
            f"{total_return:.2f}%" if total_return is not None else "N/A"
        )

        console.print(summary)

@click.group()
def snapshot():
    pass

@snapshot.command()
@click.option("--investment-id", "-i", type=int, required=True)
@click.option("--value", "-v", required=True)
@click.option("--date", "snapshot_date")
def create(investment_id, value, snapshot_date):
    from datetime import date

    user_id = current_user_id()

    with Session(db_engine) as session:
        account_item = session.scalar(
            select(InvestmentAccount).where(
                InvestmentAccount.investment_id == investment_id,
                InvestmentAccount.user_id == user_id
            )
        )

        if not account_item:
            error("Investment account not found.")
            return

        item = InvestmentSnapshot(
            investment_id=investment_id,
            value=money(value),
            snapshot_date=(
                date.fromisoformat(snapshot_date)
                if snapshot_date else date.today()
            )
        )

        if item.value < 0:
            raise click.BadParameter("Investment value cannot be negative.")

        session.add(item)

        try:
            session.commit()
            success("Investment snapshot recorded!")
        except Exception:
            session.rollback()
            error("A snapshot already exists for this investment on that date.")


@snapshot.command()
@click.option("--investment-id", "-i", type=int, required=False)
def list_snapshots(investment_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        stmt = (
            select(InvestmentSnapshot)
            .join(InvestmentAccount)
            .where(InvestmentAccount.user_id == user_id)
        )

        if investment_id is not None:
            stmt = stmt.where(
                InvestmentSnapshot.investment_id == investment_id
            )

        records = session.scalars(
            stmt.order_by(InvestmentSnapshot.snapshot_date.desc())
        ).all()

        table = Table(title="Investment Snapshots")
        table.add_column("ID")
        table.add_column("Investment ID")
        table.add_column("Date")
        table.add_column("Value", justify="right")

        for item in records:
            table.add_row(
                str(item.snapshot_id),
                str(item.investment_id),
                str(item.snapshot_date),
                f"{item.value:,.2f}"
            )

        console.print(table)


@snapshot.command()
@click.option("--snapshot-id", "-i", type=int, required=True)
def delete(snapshot_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(InvestmentSnapshot)
            .join(InvestmentAccount)
            .where(
                InvestmentSnapshot.snapshot_id == snapshot_id,
                InvestmentAccount.user_id == user_id
            )
        )

        if not item:
            error("Snapshot not found.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Snapshot deleted!")



@click.group()
def investment_transaction():
    pass


@investment_transaction.command()
@click.option("--investment-id", "-i", type=int, required=True)
@click.option("--type", "transaction_type", required=True,
              type=click.Choice(["contribution", "withdrawal"]))
@click.option("--amount", "-a", required=True)
@click.option("--date", "transaction_date")
def create(investment_id, transaction_type, amount, transaction_date):
    from datetime import date

    user_id = current_user_id()

    with Session(db_engine) as session:
        account_item = session.scalar(
            select(InvestmentAccount).where(
                InvestmentAccount.investment_id == investment_id,
                InvestmentAccount.user_id == user_id
            )
        )

        if not account_item:
            error("Investment account not found.")
            return

        item = InvestmentTransaction(
            investment_id=investment_id,
            transaction_type=InvestmentTransactionType(transaction_type),
            amount=money(amount),
            transaction_date=(
                date.fromisoformat(transaction_date)
                if transaction_date else date.today()
            )
        )

        if item.amount <= 0:
            raise click.BadParameter("Amount must be greater than zero.")

        session.add(item)
        session.commit()

    success("Investment transaction recorded!")


@investment_transaction.command()
def list_transactions():
    user_id = current_user_id()

    with Session(db_engine) as session:
        records = session.scalars(
            select(InvestmentTransaction)
            .join(InvestmentAccount)
            .where(InvestmentAccount.user_id == user_id)
            .order_by(InvestmentTransaction.transaction_date.desc())
        ).all()

        table = Table(title="Investment Transactions")
        table.add_column("ID")
        table.add_column("Investment ID")
        table.add_column("Type")
        table.add_column("Date")
        table.add_column("Amount", justify="right")

        for item in records:
            table.add_row(
                str(item.transaction_id),
                str(item.investment_id),
                item.transaction_type.value,
                str(item.transaction_date),
                f"{item.amount:,.2f}"
            )

        console.print(table)


@investment_transaction.command()
@click.option("--transaction-id", "-i", type=int, required=True)
def delete(transaction_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(InvestmentTransaction)
            .join(InvestmentAccount)
            .where(
                InvestmentTransaction.transaction_id == transaction_id,
                InvestmentAccount.user_id == user_id
            )
        )

        if not item:
            error("Investment transaction not found.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Investment transaction deleted!")

@click.group()
def goal():
    pass


@goal.command()
@click.option("--name", "-n", required=True)
@click.option("--target", "-t", required=True)
@click.option("--start-date", default=None)
@click.option("--end-date", required=True)
def create(name, target, start_date, end_date):
    from datetime import date

    user_id = current_user_id()

    item = SavingsGoal(
        goal_name=name,
        target_amount=money(target),
        start_date=(
            date.fromisoformat(start_date)
            if start_date else date.today()
        ),
        end_date=date.fromisoformat(end_date),
        user_id=user_id
    )

    if item.target_amount <= 0:
        raise click.BadParameter("Target must be greater than zero.")

    if item.end_date < item.start_date:
        raise click.BadParameter("End date cannot be before start date.")

    with Session(db_engine) as session:
        session.add(item)
        session.commit()

    success("Savings goal created!")


@goal.command()
def list_goals():
    user_id = current_user_id()

    with Session(db_engine) as session:
        records = session.scalars(
            select(SavingsGoal).where(SavingsGoal.user_id == user_id)
        ).all()

        table = Table(title="My Savings Goals")
        table.add_column("ID")
        table.add_column("Goal")
        table.add_column("Target", justify="right")
        table.add_column("Start Date")
        table.add_column("End Date")
        table.add_column("Saved", justify="right")

        for item in records:
            saved = sum(
                (c.amount for c in item.contributions),
                Decimal("0.00")
            )

            table.add_row(
                str(item.goal_id),
                item.goal_name,
                f"{item.target_amount:,.2f}",
                str(item.start_date),
                str(item.end_date),
                f"{saved:,.2f}"
            )

        console.print(table)


@goal.command()
@click.option("--goal-id", "-i", type=int, required=True)
@click.option("--name", "-n")
@click.option("--target", "-t")
@click.option("--start-date")
@click.option("--end-date")
def update(goal_id, name, target, start_date, end_date):
    from datetime import date

    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(SavingsGoal).where(
                SavingsGoal.goal_id == goal_id,
                SavingsGoal.user_id == user_id
            )
        )

        if not item:
            error("Savings goal not found.")
            return

        if name is not None:
            item.goal_name = name

        if target is not None:
            item.target_amount = money(target)

        if start_date is not None:
            item.start_date = date.fromisoformat(start_date)

        if end_date is not None:
            item.end_date = date.fromisoformat(end_date)

        if item.target_amount <= 0:
            raise click.BadParameter("Target must be greater than zero.")

        if item.end_date < item.start_date:
            raise click.BadParameter("End date cannot be before start date.")

        session.commit()

    success("Savings goal updated!")


@goal.command()
@click.option("--goal-id", "-i", type=int, required=True)
def delete(goal_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(SavingsGoal).where(
                SavingsGoal.goal_id == goal_id,
                SavingsGoal.user_id == user_id
            )
        )

        if not item:
            error("Savings goal not found.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Savings goal and its contributions deleted!")



@click.group()
def contribution():
    pass


@contribution.command()
@click.option("--goal-id", "-g", type=int, required=True)
@click.option("--amount", "-a", required=True)
@click.option("--account-id", "-c", type=int, required=False)
@click.option("--date", "contribution_date")
def create(goal_id, amount, account_id, contribution_date):
    from datetime import date

    user_id = current_user_id()

    with Session(db_engine) as session:
        goal_item = session.scalar(
            select(SavingsGoal).where(
                SavingsGoal.goal_id == goal_id,
                SavingsGoal.user_id == user_id
            )
        )

        if not goal_item:
            error("Savings goal not found.")
            return

        if account_id is not None:
            account_item = session.scalar(
                select(Accounts).where(
                    Accounts.account_id == account_id,
                    Accounts.user_id == user_id
                )
            )

            if not account_item:
                error("Account not found.")
                return

        item = GoalContribution(
            goal_id=goal_id,
            amount=money(amount),
            account_id=account_id,
            contribution_date=(
                date.fromisoformat(contribution_date)
                if contribution_date else date.today()
            )
        )

        if item.amount <= 0:
            raise click.BadParameter("Contribution must be greater than zero.")

        session.add(item)
        session.commit()

    success("Goal contribution recorded!")


@contribution.command()
@click.option("--goal-id", "-g", type=int, required=False)
def list_contributions(goal_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        stmt = (
            select(GoalContribution)
            .join(SavingsGoal)
            .where(SavingsGoal.user_id == user_id)
        )

        if goal_id is not None:
            stmt = stmt.where(GoalContribution.goal_id == goal_id)

        records = session.scalars(
            stmt.order_by(GoalContribution.contribution_date.desc())
        ).all()

        table = Table(title="Savings Contributions")
        table.add_column("ID")
        table.add_column("Goal ID")
        table.add_column("Account ID")
        table.add_column("Date")
        table.add_column("Amount", justify="right")

        for item in records:
            table.add_row(
                str(item.contribution_id),
                str(item.goal_id),
                str(item.account_id or "-"),
                str(item.contribution_date),
                f"{item.amount:,.2f}"
            )

        console.print(table)


@contribution.command()
@click.option("--contribution-id", "-i", type=int, required=True)
def delete(contribution_id):
    user_id = current_user_id()

    with Session(db_engine) as session:
        item = session.scalar(
            select(GoalContribution)
            .join(SavingsGoal)
            .where(
                GoalContribution.contribution_id == contribution_id,
                SavingsGoal.user_id == user_id
            )
        )

        if not item:
            error("Contribution not found.")
            return

        if not confirm_delete():
            return

        session.delete(item)
        session.commit()

    success("Contribution deleted!")


@click.group()
def report():
    pass

@report.command()
def show():
    user_id = current_user_id()

    with Session(db_engine) as session:

        transactions = session.scalars(
            select(Transaction)
            .join(Accounts)
            .join(Categories)
            .where(Accounts.user_id == user_id)
        ).all()

        total_income = sum(
            (
                item.amount for item in transactions
                if item.category.category_type == CategoryType.INCOME
            ),
            Decimal("0.00")
        )

        total_expenses = sum(
            (
                item.amount for item in transactions
                if item.category.category_type == CategoryType.EXPENSE
            ),
            Decimal("0.00")
        )

        net_cash_flow = total_income - total_expenses

        investments = session.scalars(
            select(InvestmentAccount).where(
                InvestmentAccount.user_id == user_id
            )
        ).all()

        total_contributions = Decimal("0.00")
        total_withdrawals = Decimal("0.00")
        total_valuation = Decimal("0.00")
        investments_without_snapshot = 0

        for investment in investments:

            investment_transactions = session.scalars(
                select(InvestmentTransaction).where(
                    InvestmentTransaction.investment_id
                    == investment.investment_id
                )
            ).all()

            for item in investment_transactions:

                if item.transaction_type == InvestmentTransactionType.CONTRIBUTION:
                    total_contributions += item.amount

                elif item.transaction_type == InvestmentTransactionType.WITHDRAWAL:
                    total_withdrawals += item.amount

            latest_snapshot = session.scalar(
                select(InvestmentSnapshot)
                .where(
                    InvestmentSnapshot.investment_id
                    == investment.investment_id
                )
                .order_by(InvestmentSnapshot.snapshot_date.desc())
                .limit(1)
            )

            if latest_snapshot:
                total_valuation += latest_snapshot.value
            else:
                investments_without_snapshot += 1

        net_invested = total_contributions - total_withdrawals

        investment_gain = total_valuation - net_invested

        goals = session.scalars(
            select(SavingsGoal).where(
                SavingsGoal.user_id == user_id
            )
        ).all()

        total_goal_target = Decimal("0.00")
        total_goal_contributions = Decimal("0.00")

        for goal_item in goals:

            total_goal_target += goal_item.target_amount

            total_goal_contributions += sum(
                (
                    item.amount
                    for item in goal_item.contributions
                ),
                Decimal("0.00")
            )

        goal_remaining = max(
            total_goal_target - total_goal_contributions,
            Decimal("0.00")
        )

        goal_progress_percentage = (
            total_goal_contributions / total_goal_target * 100
            if total_goal_target > 0
            else Decimal("0.00")
        )

        table = Table(title="PERSONAL FINANCE REPORT")

        table.add_column("Financial Metric")
        table.add_column("Amount", justify="right")

        
        table.add_section()
        table.add_row("[bold cyan]TRANSACTION SUMMARY[/bold cyan]", "")

        table.add_row("Total Income", f"{total_income:,.2f}")
        table.add_row("Total Expenses", f"{total_expenses:,.2f}")
        table.add_row("Net Cash Flow", f"{net_cash_flow:,.2f}")

        
        table.add_section()
        table.add_row("[bold cyan]INVESTMENT SUMMARY[/bold cyan]", "")

        table.add_row(
            "Total Contributions",
            f"{total_contributions:,.2f}"
        )
        table.add_row(
            "Total Withdrawals",
            f"{total_withdrawals:,.2f}"
        )
        table.add_row(
            "Net Invested",
            f"{net_invested:,.2f}"
        )
        table.add_row(
            "Latest Investment Valuations",
            f"{total_valuation:,.2f}"
        )
        table.add_row(
            "Investment Gain/Loss (partial if snapshots missing)",
            f"{investment_gain:,.2f}"
        )

        if investments_without_snapshot:
            table.add_row(
                "Investments Without Snapshots",
                str(investments_without_snapshot)
            )

        
        table.add_section()
        table.add_row("[bold cyan]SAVINGS GOALS[/bold cyan]", "")

        table.add_row(
            "Total Savings Targets",
            f"{total_goal_target:,.2f}"
        )
        table.add_row(
            "Total Goal Contributions",
            f"{total_goal_contributions:,.2f}"
        )
        table.add_row(
            "Remaining Savings Target",
            f"{goal_remaining:,.2f}"
        )
        table.add_row(
            "Overall Goal Progress",
            f"{goal_progress_percentage:.2f}%"
        )

        console.print(table)

        print(
            "\n[bold green]Financial report generated successfully![/bold green]"
        )