from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import BillingRequired, current_user, flash, get_active_profile, require_user, template_context
from ..models import AnalysisNote, TradeLog, TradingPlan, TradingProfile, User
from ..plans import plan_limits
from ..security import hash_password, is_safe_next, valid_email, verify_password
from ..templating import render

router = APIRouter()


def _create_default_profile(db: Session, user: User) -> TradingProfile:
    profile = TradingProfile(
        user_id=user.id,
        name="Main Journal",
        markets="XAU · BTC",
        style="Intraday",
        experience="Developing",
        goal="Track process, not just PnL.",
        starting_balance=0.0,
        max_trades_per_day=3,
        session_asia=False,
        session_london=True,
        session_newyork=True,
        focus_xau=True,
        focus_btc=True,
        is_default=True,
    )
    db.add(profile)
    db.flush()
    return profile


@router.get("/login")
def login_form(request: Request, next: str = "/journey", user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse(url="/journey", status_code=303)
    return render(
        "login.html",
        template_context(request, user=user, next_url=is_safe_next(next), title="Sign in"),
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/journey"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.hashed_password):
        flash(request, "Email or password is incorrect.", "error")
        return render(
            "login.html",
            template_context(request, next_url=is_safe_next(next), title="Sign in"),
            status_code=400,
        )
    request.session["user_id"] = user.id
    default_profile = (
        db.query(TradingProfile)
        .filter(TradingProfile.user_id == user.id, TradingProfile.is_default.is_(True))
        .first()
    )
    if default_profile:
        request.session["profile_id"] = default_profile.id
    flash(request, f"Welcome back, {user.display_name}.", "success")
    return RedirectResponse(url=is_safe_next(next), status_code=303)


@router.get("/register")
def register_form(request: Request, user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse(url="/journey", status_code=303)
    return render(
        "register.html",
        template_context(request, user=user, title="Create account"),
    )


@router.post("/register")
def register(
    request: Request,
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    starting_balance: float = Form(0),
    db: Session = Depends(get_db),
):
    email_clean = email.strip().lower()
    name = display_name.strip()
    if not valid_email(email_clean):
        flash(request, "Enter a valid email address.", "error")
        return render("register.html", template_context(request, title="Create account"), status_code=400)
    if len(password) < 8:
        flash(request, "Password must be at least 8 characters.", "error")
        return render("register.html", template_context(request, title="Create account"), status_code=400)
    if len(name) < 2:
        flash(request, "Add a display name.", "error")
        return render("register.html", template_context(request, title="Create account"), status_code=400)
    if db.query(User).filter(User.email == email_clean).first():
        flash(request, "That email is already registered. Sign in instead.", "error")
        return RedirectResponse(url="/login", status_code=303)

    user = User(
        email=email_clean,
        hashed_password=hash_password(password),
        display_name=name[:80],
        plan="free",
        subscription_status="inactive",
    )
    db.add(user)
    db.flush()
    profile = _create_default_profile(db, user)
    profile.starting_balance = starting_balance
    if db.query(User).count() == 1:
        db.query(TradeLog).filter(TradeLog.user_id.is_(None)).update(
            {"user_id": user.id, "profile_id": profile.id}, synchronize_session=False
        )
        db.query(TradingPlan).filter(TradingPlan.user_id.is_(None)).update(
            {"user_id": user.id, "profile_id": profile.id}, synchronize_session=False
        )
        db.query(AnalysisNote).filter(AnalysisNote.user_id.is_(None)).update(
            {"user_id": user.id, "profile_id": profile.id}, synchronize_session=False
        )
    db.commit()
    request.session["user_id"] = user.id
    request.session["profile_id"] = profile.id
    flash(request, "Account created. Set trades from your start balance.", "success")
    return RedirectResponse(url="/journey", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/account")
def account_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "account.html",
        template_context(request, user=user, profile=profile, title="Account"),
    )


@router.post("/account")
def update_account(
    request: Request,
    display_name: str = Form(...),
    starting_balance: float = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    name = display_name.strip()
    if len(name) < 2:
        flash(request, "Name is too short.", "error")
        return RedirectResponse(url="/account", status_code=303)
    user.display_name = name[:80]
    profile.starting_balance = starting_balance
    db.commit()
    flash(request, "Saved.", "success")
    return RedirectResponse(url="/account", status_code=303)


@router.get("/personal")
def personal_page(
    request: Request,
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "personal.html",
        template_context(request, user=user, profile=profile, title="Personal"),
    )


@router.post("/personal")
def update_personal(
    request: Request,
    max_trades_per_day: int = Form(3),
    starting_balance: float = Form(0),
    session_asia: str | None = Form(None),
    session_london: str | None = Form(None),
    session_newyork: str | None = Form(None),
    focus_xau: str | None = Form(None),
    focus_btc: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    profile.max_trades_per_day = max(1, min(int(max_trades_per_day or 3), 20))
    profile.starting_balance = starting_balance
    asia = session_asia is not None
    london = session_london is not None
    newyork = session_newyork is not None
    if not asia and not london and not newyork:
        london = True
        newyork = True
    profile.session_asia = asia
    profile.session_london = london
    profile.session_newyork = newyork
    xau = focus_xau is not None
    btc = focus_btc is not None
    if not xau and not btc:
        xau = True
        btc = True
    profile.focus_xau = xau
    profile.focus_btc = btc
    profile.markets = " · ".join(
        part for part, enabled in (("XAU", xau), ("BTC", btc)) if enabled
    )
    db.commit()
    flash(request, "Personal desk saved.", "success")
    return RedirectResponse(url="/personal", status_code=303)


@router.get("/profiles/new")
def new_profile_form(request: Request, user: User = Depends(require_user)):
    limits = plan_limits(user)
    return render(
        "profile_form.html",
        template_context(request, user=user, title="New profile", max_profiles=limits["profiles"]),
    )


@router.post("/profiles")
def create_profile(
    request: Request,
    name: str = Form(...),
    markets: str = Form("Crypto"),
    style: str = Form("Intraday"),
    experience: str = Form("Developing"),
    goal: str = Form(""),
    bio: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    count = db.query(TradingProfile).filter(TradingProfile.user_id == user.id).count()
    max_profiles = plan_limits(user)["profiles"]
    if max_profiles is not None and count >= max_profiles:
        raise BillingRequired("Your plan is out of trading profiles. Upgrade to add another desk.")
    title = name.strip()
    if len(title) < 2:
        flash(request, "Give this profile a name.", "error")
        return RedirectResponse(url="/profiles/new", status_code=303)
    profile = TradingProfile(
        user_id=user.id,
        name=title[:80],
        markets="XAU · BTC",
        style=style.strip()[:80] or "Intraday",
        experience=experience.strip()[:40] or "Developing",
        goal=goal.strip(),
        bio=bio.strip(),
        max_trades_per_day=3,
        session_london=True,
        session_newyork=True,
        focus_xau=True,
        focus_btc=True,
        is_default=count == 0,
    )
    db.add(profile)
    db.commit()
    request.session["profile_id"] = profile.id
    flash(request, f"Profile “{profile.name}” is ready.", "success")
    return RedirectResponse(url="/journey", status_code=303)


@router.post("/profiles/{profile_id}/activate")
def activate_profile(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    profile = db.get(TradingProfile, profile_id)
    if not profile or profile.user_id != user.id:
        flash(request, "Profile not found.", "error")
        return RedirectResponse(url="/account", status_code=303)
    request.session["profile_id"] = profile.id
    flash(request, f"Switched to {profile.name}.", "success")
    return RedirectResponse(url=request.headers.get("referer") or "/journey", status_code=303)


@router.post("/profiles/{profile_id}/delete")
def delete_profile(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    profiles = db.query(TradingProfile).filter(TradingProfile.user_id == user.id).all()
    if len(profiles) <= 1:
        flash(request, "You need at least one trading profile.", "error")
        return RedirectResponse(url="/account", status_code=303)
    profile = next((item for item in profiles if item.id == profile_id), None)
    if not profile:
        flash(request, "Profile not found.", "error")
        return RedirectResponse(url="/account", status_code=303)
    db.delete(profile)
    remaining = [item for item in profiles if item.id != profile_id]
    if profile.is_default and remaining:
        remaining[0].is_default = True
    db.commit()
    if request.session.get("profile_id") == profile_id:
        request.session["profile_id"] = remaining[0].id
    flash(request, "Profile removed.", "success")
    return RedirectResponse(url="/account", status_code=303)
