from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import BillingRequired, flash, get_active_profile, require_user, template_context
from ..models import LearningResource, MarketCondition, SetupEntry, TradingProfile, User
from ..plans import plan_limits
from ..storage import UploadError, delete_file, save_upload
from ..templating import render

router = APIRouter()


@router.get("/entries")
def list_entries(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    items = db.scalars(
        select(SetupEntry)
        .where(SetupEntry.user_id == user.id, SetupEntry.profile_id == profile.id)
        .order_by(SetupEntry.created_at.desc())
    ).all()
    return render(
        "entries.html",
        template_context(request, user=user, profile=profile, entries=items, title="Good entries"),
    )


@router.get("/entries/new")
def new_entry_form(
    request: Request,
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "entry_form.html",
        template_context(request, user=user, profile=profile, title="Post a good entry"),
    )


@router.post("/entries")
def create_entry(
    request: Request,
    title: str = Form(...),
    pair: str = Form(...),
    direction: str = Form("long"),
    market_condition: str = Form("Trend"),
    why_good: str = Form(...),
    tags: str = Form(""),
    chart_image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    cap = plan_limits(user)["entries"]
    used = db.scalar(select(func.count()).select_from(SetupEntry).where(SetupEntry.user_id == user.id)) or 0
    if cap is not None and used >= cap:
        raise BillingRequired("Good-entry limit reached on this plan. Upgrade to keep posting setups.")

    image_path = None
    if chart_image and chart_image.filename:
        try:
            image_path = save_upload(chart_image, user.id, "image", db)
        except UploadError as exc:
            flash(request, exc.message, "error")
            return RedirectResponse(url="/entries/new", status_code=303)

    db.add(
        SetupEntry(
            user_id=user.id,
            profile_id=profile.id,
            title=title.strip(),
            pair=pair.strip().upper(),
            direction=direction.strip().lower(),
            market_condition=market_condition.strip(),
            why_good=why_good.strip(),
            tags=tags.strip(),
            image_path=image_path,
        )
    )
    db.commit()
    flash(request, "Good entry saved to your library.", "success")
    return RedirectResponse(url="/entries", status_code=303)


@router.post("/entries/{entry_id}/delete")
def delete_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    entry = db.get(SetupEntry, entry_id)
    if entry and entry.user_id == user.id:
        delete_file(entry.image_path)
        db.delete(entry)
        db.commit()
        flash(request, "Entry removed.", "success")
    return RedirectResponse(url="/entries", status_code=303)


@router.get("/conditions")
def list_conditions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    items = db.scalars(
        select(MarketCondition)
        .where(MarketCondition.user_id == user.id, MarketCondition.profile_id == profile.id)
        .order_by(MarketCondition.note_date.desc(), MarketCondition.id.desc())
    ).all()
    return render(
        "conditions.html",
        template_context(request, user=user, profile=profile, conditions=items, title="Market conditions"),
    )


@router.get("/conditions/new")
def new_condition_form(
    request: Request,
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "condition_form.html",
        template_context(request, user=user, profile=profile, today=date.today().isoformat(), title="Market note"),
    )


@router.post("/conditions")
def create_condition(
    request: Request,
    note_date: str = Form(...),
    market: str = Form(...),
    trend: str = Form(...),
    volatility: str = Form(...),
    session: str = Form("All day"),
    summary: str = Form(...),
    catalysts: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    day = date.fromisoformat(note_date)
    cap = plan_limits(user)["conditions_per_month"]
    used = db.scalar(
        select(func.count())
        .select_from(MarketCondition)
        .where(MarketCondition.user_id == user.id)
        .where(extract("year", MarketCondition.note_date) == day.year)
        .where(extract("month", MarketCondition.note_date) == day.month)
    ) or 0
    if cap is not None and used >= cap:
        raise BillingRequired("This month's market-note limit is reached. Upgrade to keep logging conditions.")

    db.add(
        MarketCondition(
            user_id=user.id,
            profile_id=profile.id,
            note_date=day,
            market=market.strip().upper(),
            trend=trend.strip(),
            volatility=volatility.strip(),
            session=session.strip(),
            summary=summary.strip(),
            catalysts=catalysts.strip(),
        )
    )
    db.commit()
    flash(request, "Market condition posted.", "success")
    return RedirectResponse(url="/conditions", status_code=303)


@router.post("/conditions/{condition_id}/delete")
def delete_condition(
    condition_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    note = db.get(MarketCondition, condition_id)
    if note and note.user_id == user.id:
        db.delete(note)
        db.commit()
        flash(request, "Market note removed.", "success")
    return RedirectResponse(url="/conditions", status_code=303)


@router.get("/library")
def list_library(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    items = db.scalars(
        select(LearningResource)
        .where(LearningResource.user_id == user.id, LearningResource.profile_id == profile.id)
        .order_by(LearningResource.created_at.desc())
    ).all()
    return render(
        "library.html",
        template_context(request, user=user, profile=profile, resources=items, title="Learn"),
    )


@router.get("/library/new")
def new_library_form(
    request: Request,
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    return render(
        "library_form.html",
        template_context(request, user=user, profile=profile, title="Upload PDF"),
    )


@router.post("/library")
def create_library_item(
    request: Request,
    title: str = Form(...),
    category: str = Form("Playbook"),
    notes: str = Form(""),
    pdf_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    profile: TradingProfile = Depends(get_active_profile),
):
    cap = plan_limits(user)["pdfs"]
    used = db.scalar(select(func.count()).select_from(LearningResource).where(LearningResource.user_id == user.id)) or 0
    if cap == 0:
        raise BillingRequired("PDF library is included on Trader and Pro.")
    if cap is not None and used >= cap:
        raise BillingRequired("PDF limit reached. Upgrade to Pro for an unlimited library.")

    try:
        filename = save_upload(pdf_file, user.id, "pdf", db)
    except UploadError as exc:
        flash(request, exc.message, "error")
        return RedirectResponse(url="/library/new", status_code=303)

    db.add(
        LearningResource(
            user_id=user.id,
            profile_id=profile.id,
            title=title.strip(),
            category=category.strip() or "Playbook",
            filename=filename,
            original_name=pdf_file.filename or filename,
            notes=notes.strip(),
        )
    )
    db.commit()
    flash(request, "PDF added to your learning library.", "success")
    return RedirectResponse(url="/library", status_code=303)


@router.post("/library/{resource_id}/delete")
def delete_library_item(
    resource_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = db.get(LearningResource, resource_id)
    if item and item.user_id == user.id:
        delete_file(item.filename)
        db.delete(item)
        db.commit()
        flash(request, "PDF removed.", "success")
    return RedirectResponse(url="/library", status_code=303)
