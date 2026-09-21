from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .database import get_db
from .models import TradingProfile, User
from .plans import PLANS, effective_plan, plan_limits


class LoginRequired(Exception):
    def __init__(self, next_url: str = "/journey"):
        self.next_url = next_url


class BillingRequired(Exception):
    def __init__(self, message: str = "Upgrade your plan to use this."):
        self.message = message


def flash(request: Request, message: str, category: str = "info") -> None:
    messages = request.session.get("flash") or []
    messages.append({"message": message, "category": category})
    request.session["flash"] = messages


def pop_flash(request: Request) -> list[dict]:
    return request.session.pop("flash", [])


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        return None
    request.state.user = user
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user(request, db)
    if not user:
        raise LoginRequired(str(request.url.path))
    return user


def get_active_profile(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TradingProfile:
    profiles = db.query(TradingProfile).filter(TradingProfile.user_id == user.id).order_by(
        TradingProfile.is_default.desc(), TradingProfile.id
    ).all()
    if not profiles:
        profile = TradingProfile(
            user_id=user.id,
            name="Main Journal",
            markets="XAU · BTC",
            style="Intraday",
            experience="Developing",
            max_trades_per_day=3,
            session_asia=False,
            session_london=True,
            session_newyork=True,
            focus_xau=True,
            focus_btc=True,
            is_default=True,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        profiles = [profile]

    selected_id = request.session.get("profile_id")
    profile = next((item for item in profiles if item.id == selected_id), None)
    if profile is None:
        profile = next((item for item in profiles if item.is_default), profiles[0])
        request.session["profile_id"] = profile.id
    request.state.profile = profile
    request.state.profiles = profiles
    return profile


def focus_pairs(profile: TradingProfile | None) -> list[str]:
    if profile is None:
        return ["XAUUSD", "BTCUSDT"]
    pairs: list[str] = []
    if getattr(profile, "focus_xau", True):
        pairs.append("XAUUSD")
    if getattr(profile, "focus_btc", True):
        pairs.append("BTCUSDT")
    return pairs or ["XAUUSD", "BTCUSDT"]


def focus_sessions(profile: TradingProfile | None) -> list[str]:
    if profile is None:
        return ["London", "New York"]
    sessions: list[str] = []
    if getattr(profile, "session_asia", False):
        sessions.append("Asia")
    if getattr(profile, "session_london", True):
        sessions.append("London")
    if getattr(profile, "session_newyork", True):
        sessions.append("New York")
    return sessions or ["London"]


def template_context(request: Request, **extra):
    user = extra.get("user") or getattr(request.state, "user", None)
    profile = extra.get("profile") or getattr(request.state, "profile", None)
    profiles = extra.get("profiles") or getattr(request.state, "profiles", [])
    plan_id = effective_plan(user)
    ctx = {
        "request": request,
        "user": user,
        "profile": profile,
        "profiles": profiles,
        "flash_messages": pop_flash(request),
        "plan_id": plan_id,
        "plan": PLANS[plan_id],
        "limits": plan_limits(user),
        "now": datetime.utcnow(),
        "nav_path": request.url.path or "",
        "focus_pairs": focus_pairs(profile),
        "focus_sessions": focus_sessions(profile),
    }
    ctx.update(extra)
    if ctx.get("profile"):
        ctx.setdefault("focus_pairs", focus_pairs(ctx["profile"]))
        ctx.setdefault("focus_sessions", focus_sessions(ctx["profile"]))
    return ctx


def login_redirect(exc: LoginRequired) -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={quote(exc.next_url)}", status_code=303)
