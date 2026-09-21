from __future__ import annotations

import re
from urllib.parse import urlparse

import bcrypt

from .config import get_settings

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip().lower()))


def origin_matches_host(origin_or_referer: str | None, host: str | None) -> bool:
    if not origin_or_referer or not host:
        return False
    parsed = urlparse(origin_or_referer)
    return parsed.netloc.lower() == host.lower()


def is_safe_next(path: str | None) -> str:
    if not path:
        return "/journey"
    if not path.startswith("/") or path.startswith("//"):
        return "/journey"
    return path


def require_production_secrets() -> None:
    settings = get_settings()
    if settings.debug:
        return
    weak = {
        "change-me",
        "change-this-in-production-to-a-long-random-value",
        "local-dev-tradepath-change-before-production-use-32b",
    }
    if settings.secret_key in weak or len(settings.secret_key) < 24:
        raise RuntimeError("SECRET_KEY must be set to a strong random value in production.")
