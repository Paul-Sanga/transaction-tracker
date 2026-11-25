import sys
import bcrypt
from rich import print
from sqlalchemy.orm import Session
from sqlalchemy import select, exists
from email_validator import validate_email

from models import User
from engine import db_engine

def user_exists(email):
    with Session(db_engine) as session:

        return session.scalar(
            select(
                exists().where(User.email == email)
            )
        )

def register_validation(firstname: str, lastname: str, email: str, password: str) -> None:
    try:
        user = user_exists(email)
        if user:
            print(f"[italic red]User account already registered![/italic red]")
            sys.exit()
        else:
            password_bytes = password.encode("utf-8")
            if len(password_bytes) < 8:
                raise ValueError("Password should be at least 8 characters long")
            email_info = validate_email(email, check_deliverability=True).normalized
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(password_bytes, salt).decode("utf-8")
            return firstname, lastname, email_info, hashed
    except Exception as e:
        print(f"[italic red]{e}[/italic red]")


def login_validation(email, password):
    try:
        user = user_exists(email)
        if not user:
            print(f"[italic red]Invalid login credentials[/italic red]")
            sys.exit()
        else:
            password_bytes = password.encode("utf-8")
            with Session(db_engine) as session:
                stmt = select(User).where(User.email == email)
                user_rec = session.scalar(stmt)
                print(user_rec.email)
                if not bcrypt.checkpw(password_bytes, user_rec.password.encode("utf-8")):
                    print(f"[italic red]Invalid login credentials[/italic red]")
                else:
                    return user_rec   
    except Exception as e:
        print(f"[italic red]{e}[/italic red]")