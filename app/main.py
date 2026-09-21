from __future__ import annotations

from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import BASE_DIR, get_settings
from .database import get_db, migrate_schema
from .deps import BillingRequired, LoginRequired, current_user, flash, login_redirect, require_user, template_context
from .models import AnalysisNote, FileAsset, LearningResource, SetupEntry, TradeImage, User
from .security import origin_matches_host, require_production_secrets
from .storage import uploads_dir
from .templating import render
from .routers import auth, billing, journal, library


CSRF_EXEMPT = {"/billing/webhook", "/health"}


def create_app() -> FastAPI:
    settings = get_settings()
    require_production_secrets()
    uploads_dir()
    migrate_schema()

    app = FastAPI(title=settings.app_name, docs_url=None if not settings.debug else "/docs", redoc_url=None)

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    if settings.host_list != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.host_list)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="tradepath_session",
        https_only=settings.session_https_only,
        same_site="lax",
        max_age=60 * 60 * 24 * 30,
    )

    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    app.include_router(auth.router)
    app.include_router(billing.router)
    app.include_router(journal.router)
    app.include_router(library.router)

    @app.middleware("http")
    async def csrf_origin_guard(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path not in CSRF_EXEMPT:
            origin = request.headers.get("origin") or request.headers.get("referer")
            host = request.headers.get("host")
            if origin and not origin_matches_host(origin, host):
                return RedirectResponse(url="/", status_code=303)
        return await call_next(request)

    @app.exception_handler(LoginRequired)
    async def login_required_handler(request: Request, exc: LoginRequired):
        return login_redirect(exc)

    @app.exception_handler(BillingRequired)
    async def billing_required_handler(request: Request, exc: BillingRequired):
        flash(request, exc.message, "error")
        return RedirectResponse(url="/billing", status_code=303)

    @app.get("/")
    def home(request: Request, user: User | None = Depends(current_user)):
        if user:
            return RedirectResponse(url="/journey", status_code=303)
        from .plans import PLANS

        return render(
            "landing.html",
            template_context(request, user=None, plans=PLANS, title=settings.app_name),
        )

    @app.get("/media/{filename}")
    def media(
        filename: str,
        db: Session = Depends(get_db),
        user: User = Depends(require_user),
    ):
        if "/" in filename or "\\" in filename or ".." in filename:
            return RedirectResponse(url="/journey", status_code=303)
        asset = db.query(FileAsset).filter(FileAsset.filename == filename, FileAsset.user_id == user.id).first()
        if not asset:
            owned = False
            image = db.query(TradeImage).filter(TradeImage.filename == filename).first()
            if image and image.trade and image.trade.user_id == user.id:
                owned = True
            note = db.query(AnalysisNote).filter(AnalysisNote.image_path == filename).first()
            if note and note.user_id == user.id:
                owned = True
            entry = db.query(SetupEntry).filter(SetupEntry.image_path == filename).first()
            if entry and entry.user_id == user.id:
                owned = True
            pdf = db.query(LearningResource).filter(LearningResource.filename == filename).first()
            if pdf and pdf.user_id == user.id:
                owned = True
            if not owned:
                return RedirectResponse(url="/journey", status_code=303)
        path = uploads_dir() / filename
        if not path.exists():
            return RedirectResponse(url="/journey", status_code=303)
        media_type = "application/pdf" if path.suffix.lower() == ".pdf" else None
        return FileResponse(path, media_type=media_type)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()
