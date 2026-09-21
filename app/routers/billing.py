from __future__ import annotations

from datetime import datetime, timedelta

import stripe
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import current_user, flash, require_user, template_context
from ..models import User
from ..plans import PLANS, effective_plan
from ..templating import render

router = APIRouter()


def _apply_plan(user: User, plan: str, subscription_id: str | None = None, customer_id: str | None = None) -> None:
    user.plan = plan
    user.subscription_status = "active"
    user.subscription_expires_at = datetime.utcnow() + timedelta(days=32)
    if subscription_id:
        user.stripe_subscription_id = subscription_id
    if customer_id:
        user.stripe_customer_id = customer_id


@router.get("/pricing")
def pricing(request: Request, user: User | None = Depends(current_user)):
    return render(
        "pricing.html",
        template_context(
            request,
            user=user,
            plans=PLANS,
            current_plan=effective_plan(user),
            stripe_enabled=get_settings().stripe_enabled,
            title="Pricing",
        ),
    )


@router.get("/billing")
def billing(request: Request, user: User = Depends(require_user)):
    settings = get_settings()
    return render(
        "billing.html",
        template_context(
            request,
            user=user,
            plans=PLANS,
            current_plan=effective_plan(user),
            stripe_enabled=settings.stripe_enabled,
            dev_billing=settings.enable_dev_billing or settings.debug,
            title="Subscription",
        ),
    )


@router.post("/billing/checkout")
def start_checkout(
    request: Request,
    plan: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if plan not in {"trader", "pro"}:
        flash(request, "Choose Trader or Pro.", "error")
        return RedirectResponse(url="/billing", status_code=303)

    settings = get_settings()
    if settings.stripe_enabled:
        stripe.api_key = settings.stripe_secret_key
        price_id = settings.stripe_price_trader if plan == "trader" else settings.stripe_price_pro
        success = (settings.public_base_url or str(request.base_url).rstrip("/")) + "/billing/success"
        cancel = (settings.public_base_url or str(request.base_url).rstrip("/")) + "/billing"
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=user.email,
            client_reference_id=str(user.id),
            success_url=success + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": str(user.id), "plan": plan},
            allow_promotion_codes=True,
        )
        return RedirectResponse(url=session.url, status_code=303)

    if settings.enable_dev_billing or settings.debug:
        _apply_plan(user, plan)
        db.commit()
        flash(request, f"{PLANS[plan]['name']} is active on this account.", "success")
        return RedirectResponse(url="/billing", status_code=303)

    flash(request, "Payments are not configured yet. Set Stripe keys on the server.", "error")
    return RedirectResponse(url="/billing", status_code=303)


@router.get("/billing/success")
def billing_success(request: Request, session_id: str | None = None, user: User = Depends(require_user)):
    flash(request, "Subscription checkout complete. Access updates in a few seconds.", "success")
    return RedirectResponse(url="/billing", status_code=303)


@router.post("/billing/cancel")
def cancel_local_plan(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    settings = get_settings()
    if settings.stripe_enabled and user.stripe_subscription_id:
        stripe.api_key = settings.stripe_secret_key
        stripe.Subscription.cancel(user.stripe_subscription_id)
    user.plan = "free"
    user.subscription_status = "canceled"
    user.stripe_subscription_id = None
    db.commit()
    flash(request, "You are back on the Starter plan.", "success")
    return RedirectResponse(url="/billing", status_code=303)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.stripe_enabled:
        return JSONResponse({"ok": False, "error": "stripe disabled"}, status_code=400)
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    stripe.api_key = settings.stripe_secret_key
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)

    data = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        user_id = (data.get("metadata") or {}).get("user_id") or data.get("client_reference_id")
        plan = (data.get("metadata") or {}).get("plan") or "trader"
        if user_id:
            user = db.get(User, int(user_id))
            if user:
                _apply_plan(
                    user,
                    plan if plan in PLANS else "trader",
                    subscription_id=data.get("subscription"),
                    customer_id=data.get("customer"),
                )
                db.commit()
    elif event["type"] in {"customer.subscription.updated", "customer.subscription.deleted"}:
        sub_id = data.get("id")
        status = data.get("status")
        user = db.query(User).filter(User.stripe_subscription_id == sub_id).first()
        if user:
            if status in {"active", "trialing"}:
                user.subscription_status = status
                price_id = ""
                items = (data.get("items") or {}).get("data") or []
                if items:
                    price_id = ((items[0] or {}).get("price") or {}).get("id") or ""
                if price_id == settings.stripe_price_pro:
                    user.plan = "pro"
                elif price_id == settings.stripe_price_trader:
                    user.plan = "trader"
            else:
                user.subscription_status = status or "canceled"
                if status in {"canceled", "unpaid", "incomplete_expired"}:
                    user.plan = "free"
            db.commit()
    return {"ok": True}


def raise_if_limited(user: User, used: int, cap, message: str) -> None:
    if cap is not None and used >= cap:
        raise BillingRequired(message)
