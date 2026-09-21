from __future__ import annotations

import fcntl
import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

Base = declarative_base()
_engine = None
SessionLocal = None


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql") and "sslmode=" not in url and os.getenv("RENDER"):
        joiner = "&" if "?" in url else "?"
        url = f"{url}{joiner}sslmode=require"
    return url


def _sqlite_file(url: str) -> Path | None:
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or not parsed.database:
        return None
    return Path(parsed.database)


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _connection_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine():
    global _engine, SessionLocal
    if _engine is None:
        settings = get_settings()
        url = _normalize_db_url(settings.database_url)
        sqlite_path = _sqlite_file(url)
        if sqlite_path:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        if url.startswith("sqlite"):
            _configure_sqlite(_engine)
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


def _add_column(conn, table: str, column: str, coltype: str) -> None:
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns(table)}
    if column in existing:
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))


def _schema_lock_path(engine: Engine) -> Path:
    sqlite_path = _sqlite_file(str(engine.url))
    if sqlite_path:
        return sqlite_path.with_name(".schema.lock")
    return Path("/tmp/tradepath-schema.lock")


def migrate_schema() -> None:
    from . import models  # noqa: F401

    engine = get_engine()
    lock_path = _schema_lock_path(engine)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            try:
                Base.metadata.create_all(bind=engine)
            except OperationalError as exc:
                if "already exists" not in str(exc).lower():
                    raise
            with engine.begin() as conn:
                for table in ("trade_logs", "trading_plans", "analysis_notes"):
                    _add_column(conn, table, "user_id", "INTEGER")
                    _add_column(conn, table, "profile_id", "INTEGER")
                _add_column(conn, "trading_profiles", "starting_balance", "FLOAT")
                _add_column(conn, "trading_profiles", "max_trades_per_day", "INTEGER")
                flag_type = "BOOLEAN" if engine.dialect.name == "postgresql" else "INTEGER"
                for col in ("session_asia", "session_london", "session_newyork", "focus_xau", "focus_btc"):
                    _add_column(conn, "trading_profiles", col, flag_type)
                yes, no = ("TRUE", "FALSE") if engine.dialect.name == "postgresql" else ("1", "0")
                try:
                    conn.execute(text("UPDATE trading_profiles SET starting_balance = 0 WHERE starting_balance IS NULL"))
                    conn.execute(text("UPDATE trading_profiles SET max_trades_per_day = 3 WHERE max_trades_per_day IS NULL"))
                    conn.execute(text(f"UPDATE trading_profiles SET session_london = {yes} WHERE session_london IS NULL"))
                    conn.execute(text(f"UPDATE trading_profiles SET session_newyork = {yes} WHERE session_newyork IS NULL"))
                    conn.execute(text(f"UPDATE trading_profiles SET session_asia = {no} WHERE session_asia IS NULL"))
                    conn.execute(text(f"UPDATE trading_profiles SET focus_xau = {yes} WHERE focus_xau IS NULL"))
                    conn.execute(text(f"UPDATE trading_profiles SET focus_btc = {yes} WHERE focus_btc IS NULL"))
                except OperationalError:
                    pass
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
