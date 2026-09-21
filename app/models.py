from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    subscription_status: Mapped[str] = mapped_column(String(30), default="inactive", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    profiles: Mapped[list["TradingProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin",
    )


class TradingProfile(Base):
    __tablename__ = "trading_profiles"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_profile_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    markets: Mapped[str] = mapped_column(String(200), nullable=False, default="Crypto")
    style: Mapped[str] = mapped_column(String(80), nullable=False, default="Intraday")
    experience: Mapped[str] = mapped_column(String(40), nullable=False, default="Developing")
    goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    starting_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="profiles")


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trading_profiles.id"), nullable=True, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pair: Mapped[str] = mapped_column(String(50), nullable=False)
    market_type: Mapped[str] = mapped_column(String(20), nullable=False, default="Futures")
    session: Mapped[str] = mapped_column(String(50), nullable=False, default="London")
    pnl_amount: Mapped[float] = mapped_column(Float, nullable=False)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False, default="win")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    images: Mapped[list["TradeImage"]] = relationship(
        back_populates="trade", cascade="all, delete-orphan", lazy="selectin",
    )


class TradeImage(Base):
    __tablename__ = "trade_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    trade_id: Mapped[int] = mapped_column(Integer, ForeignKey("trade_logs.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="analysis")
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    trade: Mapped["TradeLog"] = relationship(back_populates="images")


class TradingPlan(Base):
    __tablename__ = "trading_plans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trading_profiles.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    setup_name: Mapped[str] = mapped_column(String(120), nullable=False)
    market_bias: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_rules: Mapped[str] = mapped_column(Text, nullable=False)
    execution_checklist: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AnalysisNote(Base):
    __tablename__ = "analysis_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trading_profiles.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    market: Mapped[str] = mapped_column(String(50), nullable=False)
    bias: Mapped[str] = mapped_column(String(50), nullable=False)
    lesson: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_tags: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class SetupEntry(Base):
    __tablename__ = "setup_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trading_profiles.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    pair: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="long")
    market_condition: Mapped[str] = mapped_column(String(80), nullable=False, default="Trend")
    why_good: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MarketCondition(Base):
    __tablename__ = "market_conditions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trading_profiles.id"), nullable=True, index=True)
    note_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(50), nullable=False)
    trend: Mapped[str] = mapped_column(String(40), nullable=False)
    volatility: Mapped[str] = mapped_column(String(40), nullable=False)
    session: Mapped[str] = mapped_column(String(50), nullable=False, default="All day")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    catalysts: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trading_profiles.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="Playbook")
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FileAsset(Base):
    __tablename__ = "file_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="image")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
