import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / os.getenv("DATABASE_URL")

db_engine = create_engine(f"sqlite:///{DB_PATH}")