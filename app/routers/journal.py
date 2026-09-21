from __future__ import annotations

import calendar as cal
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import BillingRequired, flash, get_active_profile, require_user, template_context
from ..models import AnalysisNote, TradeImage, TradeLog, TradingPlan, TradingProfile, User
from ..plans import plan_limits
from ..storage import UploadError, delete_file, save_upload
from ..templating import render

router = APIRouter()


def _owned_trade(db: Session, trade_id: int, user: User) -> TradeLog | None:
    trade = db.get(TradeLog, trade_id)
    if not trade or trade.user_id != user.id:
        return None
    return trade


def _month_trade_count(db: Session, user: User, day: date) -> int:
    return db.scalar(
        select(func.count())
        .select_from(TradeLog)
        .where(TradeLog.user_id == user.id)
        .where(extract("year", TradeLog.trade_date) == day.year)
        .where(extract("month", TradeLog.trade_date) == day.month)
    ) or 0


@router.get("/journey")
def journey(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    trades = db.scalars(
        select(TradeLog)
        .where(TradeLog.user_id == user.id, TradeLog.profile_id == profile.id)
        .order_by(TradeLog.trade_date.desc(), TradeLog.id.desc())
    ).all()

    total_pnl = db.scalar(
        select(func.coalesce(func.sum(TradeLog.pnl_amount), 0.0)).where(
            TradeLog.user_id == user.id, TradeLog.profile_id == profile.id
        )
    ) or 0.0
    wins = db.scalar(
        select(func.count()).select_from(TradeLog).where(
            TradeLog.user_id == user.id, TradeLog.profile_id == profile.id, TradeLog.outcome == "win"
        )
    ) or 0
    losses = db.scalar(
        select(func.count()).select_from(TradeLog).where(
            TradeLog.user_id == user.id, TradeLog.profile_id == profile.id, TradeLog.outcome == "loss"
        )
    ) or 0
    start_balance = profile.starting_balance or 0.0

    return render(
        "dashboard.html",
        template_context(
            request,
            user=user,
            profile=profile,
            trade_logs=trades,
            stats={
                "start_balance": start_balance,
                "total_pnl": total_pnl,
                "current_balance": start_balance + total_pnl,
                "wins": wins,
                "losses": losses,
            },
            title="Journey",
        ),
    )


@router.post("/balance")
def update_balance(
    request: Request,
    starting_balance: float = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    profile.starting_balance = starting_balance
    db.commit()
    flash(request, "Start balance saved.", "success")
    return RedirectResponse(url="/journey", status_code=303)


@router.get("/calendar")
def calendar_page(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    today = date.today()
    y = year or today.year
    m = month or today.month
    first_weekday, num_days = cal.monthrange(y, m)
    month_name = cal.month_name[m]

    trades = db.scalars(
        select(TradeLog)
        .where(TradeLog.user_id == user.id, TradeLog.profile_id == profile.id)
        .where(extract("year", TradeLog.trade_date) == y)
        .where(extract("month", TradeLog.trade_date) == m)
        .order_by(TradeLog.trade_date, TradeLog.id)
    ).all()

    day_map: dict[int, list] = {}
    day_pnl: dict[int, float] = {}
    for trade in trades:
        d = trade.trade_date.day
        day_map.setdefault(d, []).append(trade)
        day_pnl[d] = day_pnl.get(d, 0.0) + trade.pnl_amount

    month_total = sum(day_pnl.values())
    wins = sum(1 for value in day_pnl.values() if value > 0)
    losses = sum(1 for value in day_pnl.values() if value < 0)

    prev_m, prev_y = (m - 1, y) if m > 1 else (12, y - 1)
    next_m, next_y = (m + 1, y) if m < 12 else (1, y + 1)

    weeks: list[list] = []
    row: list = [None] * first_weekday
    for day in range(1, num_days + 1):
        row.append({
            "day": day,
            "trades": day_map.get(day, []),
            "pnl": day_pnl.get(day, 0.0),
            "has_trades": day in day_map,
            "is_today": (day == today.day and m == today.month and y == today.year),
        })
        if len(row) == 7:
            weeks.append(row)
            row = []
    if row:
        row += [None] * (7 - len(row))
        weeks.append(row)

    return render(
        "calendar.html",
        template_context(
            request,
            user=user,
            profile=profile,
            year=y,
            month=m,
            month_name=month_name,
            weeks=weeks,
            month_total=month_total,
            wins=wins,
            losses=losses,
            prev_year=prev_y,
            prev_month=prev_m,
            next_year=next_y,
            next_month=next_m,
            today=today,
            title="Calendar",
        ),
    )


@router.get("/trades/new")
def new_trade_form(
    request: Request,
    trade_date: str | None = None,
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "trade_form.html",
        template_context(request, user=user, profile=profile, prefill_date=trade_date or "", title="Add trade"),
    )


@router.post("/trades")
async def create_trade(
    request: Request,
    trade_date: str = Form(...),
    pair: str = Form(...),
    market_type: str = Form("Futures"),
    session: str = Form("Day"),
    pnl_amount: float = Form(...),
    outcome: str = Form("win"),
    notes: str = Form(""),
    chart_image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    day = date.fromisoformat(trade_date)
    cap = plan_limits(user)["trades_per_month"]
    if cap is not None and _month_trade_count(db, user, day) >= cap:
        raise BillingRequired("This month's trade limit is reached. Upgrade to keep logging.")

    result = outcome.strip().lower()
    if result not in {"win", "loss", "breakeven"}:
        result = "win" if pnl_amount >= 0 else "loss"
    if result == "loss" and pnl_amount > 0:
        pnl_amount = -abs(pnl_amount)
    if result == "win" and pnl_amount < 0:
        result = "loss"

    trade = TradeLog(
        user_id=user.id,
        profile_id=profile.id,
        trade_date=day,
        pair=pair.strip().upper(),
        market_type=market_type.strip() or "Futures",
        session=session.strip() or "Day",
        pnl_amount=pnl_amount,
        outcome=result,
        notes=notes.strip(),
    )
    db.add(trade)
    db.flush()

    if chart_image and chart_image.filename:
        try:
            saved = save_upload(chart_image, user.id, "image", db)
        except UploadError as exc:
            db.rollback()
            flash(request, exc.message, "error")
            return RedirectResponse(url="/trades/new", status_code=303)
        db.add(TradeImage(trade_id=trade.id, filename=saved, label=result, caption="Chart"))

    db.commit()
    flash(request, "Trade saved.", "success")
    return RedirectResponse(url="/journey", status_code=303)


@router.get("/trades/{trade_id}")
def trade_detail(
    trade_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    trade = _owned_trade(db, trade_id, user)
    if not trade:
        flash(request, "Trade not found.", "error")
        return RedirectResponse(url="/journey", status_code=303)
    return render(
        "trade_detail.html",
        template_context(request, user=user, profile=profile, trade=trade, title=trade.pair),
    )


@router.post("/trades/{trade_id}/images")
async def upload_trade_image(
    trade_id: int,
    request: Request,
    label: str = Form("analysis"),
    caption: str = Form(""),
    chart_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trade = _owned_trade(db, trade_id, user)
    if not trade:
        return RedirectResponse(url="/journey", status_code=303)
    try:
        saved = save_upload(chart_image, user.id, "image", db)
    except UploadError as exc:
        flash(request, exc.message, "error")
        return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)
    db.add(TradeImage(trade_id=trade_id, filename=saved, label=label.strip(), caption=caption.strip()))
    db.commit()
    flash(request, "Screenshot added.", "success")
    return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)


@router.post("/trades/{trade_id}/images/{image_id}/delete")
def delete_trade_image(
    trade_id: int,
    image_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trade = _owned_trade(db, trade_id, user)
    img = db.get(TradeImage, image_id)
    if trade and img and img.trade_id == trade_id:
        delete_file(img.filename)
        db.delete(img)
        db.commit()
    return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)


@router.post("/trades/{trade_id}/delete")
def delete_trade(
    trade_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trade = _owned_trade(db, trade_id, user)
    if trade:
        for img in trade.images:
            delete_file(img.filename)
        db.delete(trade)
        db.commit()
        flash(request, "Trade deleted.", "success")
    referer = request.headers.get("referer", "/journey")
    if "calendar" in referer:
        return RedirectResponse(url=referer, status_code=303)
    return RedirectResponse(url="/journey", status_code=303)


@router.get("/plans/new")
def new_plan_form(
    request: Request,
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "plan_form.html",
        template_context(request, user=user, profile=profile, title="Add plan"),
    )


@router.post("/plans")
def create_plan(
    request: Request,
    title: str = Form(...),
    setup_name: str = Form(...),
    market_bias: str = Form(...),
    risk_rules: str = Form(...),
    execution_checklist: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    db.add(
        TradingPlan(
            user_id=user.id,
            profile_id=profile.id,
            title=title.strip(),
            setup_name=setup_name.strip(),
            market_bias=market_bias.strip(),
            risk_rules=risk_rules.strip(),
            execution_checklist=execution_checklist.strip(),
        )
    )
    db.commit()
    flash(request, "Plan saved.", "success")
    return RedirectResponse(url="/journey", status_code=303)


@router.get("/analysis/new")
def new_analysis_form(
    request: Request,
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "analysis_form.html",
        template_context(request, user=user, profile=profile, title="Add analysis"),
    )


@router.post("/analysis")
def create_analysis(
    request: Request,
    title: str = Form(...),
    market: str = Form(...),
    bias: str = Form(...),
    lesson: str = Form(...),
    pattern_tags: str = Form(""),
    chart_image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    image_path = None
    if chart_image and chart_image.filename:
        try:
            image_path = save_upload(chart_image, user.id, "image", db)
        except UploadError as exc:
            flash(request, exc.message, "error")
            return RedirectResponse(url="/analysis/new", status_code=303)

    db.add(
        AnalysisNote(
            user_id=user.id,
            profile_id=profile.id,
            title=title.strip(),
            market=market.strip().upper(),
            bias=bias.strip(),
            lesson=lesson.strip(),
            pattern_tags=pattern_tags.strip(),
            image_path=image_path,
        )
    )
    db.commit()
    flash(request, "Analysis saved.", "success")
    return RedirectResponse(url="/journey", status_code=303)
