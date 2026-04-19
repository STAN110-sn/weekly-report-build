"""
データベース接続・セッション管理
PostgreSQL（本番）または SQLite（開発）に対応
"""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./weekly_report.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI の Depends 用 DB セッション"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """コンテキストマネージャとしての DB セッション"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """テーブルを作成"""
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def run_migrations() -> None:
    """既存テーブルに不足カラムをグレースフルに追加"""
    is_sqlite = DATABASE_URL.startswith("sqlite")

    migrations = [
        ("weekly_reports", "requests_opinions", "TEXT"),
        ("weekly_reports", "submitted_at", "DATETIME"),
        ("weekly_reports", "submitter_name", "VARCHAR(100)"),
        ("generated_reports", "model_used", "VARCHAR(100)"),
    ]

    with engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                if is_sqlite:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}"))
                conn.commit()
            except Exception:
                pass
