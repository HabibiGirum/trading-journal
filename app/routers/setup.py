from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bias import analyze_setup
from ..database import get_db
from ..deps import focus_pairs, get_active_profile, require_user, template_context
from ..models import BiasCheck, TradingProfile, User
from ..templating import render

router = APIRouter()


def _optional_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


@router.get("/setup")
def setup_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    history = db.scalars(
        select(BiasCheck)
        .where(BiasCheck.user_id == user.id, BiasCheck.profile_id == profile.id)
        .order_by(BiasCheck.created_at.desc())
        .limit(8)
    ).all()
    return render(
        "setup.html",
        template_context(
            request,
            user=user,
            profile=profile,
            history=history,
            result=None,
            form={"pair": focus_pairs(profile)[0]},
            title="Setup",
        ),
    )


@router.post("/setup")
def run_setup(
    request: Request,
    pair: str = Form("XAUUSD"),
    daily: str = Form(...),
    h4: str = Form(...),
    h1: str = Form("range"),
    structure: str = Form("mixed"),
    location: str = Form("equilibrium"),
    liquidity: str = Form("none"),
    current_price: str = Form(""),
    swing_low: str = Form(""),
    swing_high: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    result = analyze_setup(
        daily=daily,
        h4=h4,
        h1=h1,
        structure=structure,
        location=location,
        liquidity=liquidity,
        current_price=current_price,
        swing_low=swing_low,
        swing_high=swing_high,
    )
    check = BiasCheck(
        user_id=user.id,
        profile_id=profile.id,
        pair=pair.strip().upper() or focus_pairs(profile)[0],
        daily=daily,
        h4=h4,
        h1=h1,
        structure=structure,
        location=location,
        liquidity=liquidity,
        current_price=_optional_float(current_price),
        swing_low=_optional_float(swing_low),
        swing_high=_optional_float(swing_high),
        direction=result["direction"],
        strength=result["strength"],
        stop_rule=result["stop_rule"],
        summary=result["emotion"],
    )
    db.add(check)
    db.commit()
    history = db.scalars(
        select(BiasCheck)
        .where(BiasCheck.user_id == user.id, BiasCheck.profile_id == profile.id)
        .order_by(BiasCheck.created_at.desc())
        .limit(8)
    ).all()
    return render(
        "setup.html",
        template_context(
            request,
            user=user,
            profile=profile,
            history=history,
            result=result,
            pair=check.pair,
            form={
                "pair": check.pair,
                "daily": daily,
                "h4": h4,
                "h1": h1,
                "structure": structure,
                "location": location,
                "liquidity": liquidity,
                "current_price": current_price,
                "swing_low": swing_low,
                "swing_high": swing_high,
            },
            title="Setup",
        ),
    )


@router.post("/setup/{check_id}/delete")
def delete_setup(
    check_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = db.get(BiasCheck, check_id)
    if item and item.user_id == user.id:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/setup", status_code=303)
