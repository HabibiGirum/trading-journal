from __future__ import annotations

from datetime import datetime

from .models import User

PLAN_ORDER = ("free", "trader", "pro")

PLANS: dict[str, dict] = {
    "free": {
        "id": "free",
        "name": "Starter",
        "price": 0,
        "tagline": "Begin the journal.",
        "features": [
            "1 trading profile",
            "25 trades per month",
            "10 good entries",
            "10 market notes per month",
            "PDF library locked",
        ],
        "limits": {
            "profiles": 1,
            "trades_per_month": 25,
            "entries": 10,
            "conditions_per_month": 10,
            "pdfs": 0,
        },
    },
    "trader": {
        "id": "trader",
        "name": "Trader",
        "price": 9,
        "tagline": "Full process, one desk.",
        "features": [
            "2 trading profiles",
            "Unlimited trades and entries",
            "Unlimited market conditions",
            "15 learning PDFs",
            "Journey stats and calendar",
        ],
        "limits": {
            "profiles": 2,
            "trades_per_month": None,
            "entries": None,
            "conditions_per_month": None,
            "pdfs": 15,
        },
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price": 19,
        "tagline": "Every market, every playbook.",
        "features": [
            "5 trading profiles",
            "Unlimited trades, entries, and notes",
            "Unlimited PDF library",
            "Multi-market journey tracking",
            "Priority for new features",
        ],
        "limits": {
            "profiles": 5,
            "trades_per_month": None,
            "entries": None,
            "conditions_per_month": None,
            "pdfs": None,
        },
    },
}


def effective_plan(user: User | None) -> str:
    if user is None:
        return "free"
    plan = (user.plan or "free").lower()
    if plan not in PLANS:
        plan = "free"
    if plan == "free":
        return "free"
    status = (user.subscription_status or "").lower()
    if status not in {"active", "trialing"}:
        return "free"
    if user.subscription_expires_at and user.subscription_expires_at < datetime.utcnow():
        return "free"
    return plan


def plan_limits(user: User | None) -> dict:
    return PLANS[effective_plan(user)]["limits"]


def can_access(user: User | None, feature: str) -> bool:
    limits = plan_limits(user)
    value = limits.get(feature)
    return value is None or (isinstance(value, int) and value > 0)
