from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

Base = declarative_base()
_engine = None
SessionLocal = None


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def get_engine():
    global _engine, SessionLocal
    if _engine is None:
        settings = get_settings()
        url = _normalize_db_url(settings.database_url)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_db():
    if SessionLocal is None:
        get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column(conn, dialect: str, table: str, column: str, coltype: str) -> None:
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns(table)}
    if column in existing:
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))


def migrate_schema() -> None:
    from . import models  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    dialect = engine.dialect.name
    int_type = "INTEGER"
    with engine.begin() as conn:
        for table in ("trade_logs", "trading_plans", "analysis_notes"):
            _add_column(conn, dialect, table, "user_id", int_type)
            _add_column(conn, dialect, table, "profile_id", int_type)
