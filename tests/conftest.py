
import os
import pytest
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import controller
from models import Base, User

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / os.getenv("DATABASE_URL")

@pytest.fixture
def test_engine():
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def db(test_engine, monkeypatch):
    monkeypatch.setattr(controller, "db_engine", test_engine)
    return test_engine

@pytest.fixture
def test_user(db):
    with Session(db) as session:
        user = User(
            firstname="John",
            lastname="Doe",
            email="john@example.com",
            password="test-password-hash"
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        user_id = user.id
    return user_id

@pytest.fixture
def authenticated_user(test_user):
    controller.generate_token(test_user, "john@example.com")
    yield test_user
    Path(controller.auth_file).unlink(missing_ok=True)