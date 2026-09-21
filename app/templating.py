from __future__ import annotations

from fastapi.templating import Jinja2Templates

from .config import BASE_DIR, get_settings

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["app_name"] = get_settings().app_name


def render(name: str, context: dict, status_code: int = 200):
    return templates.TemplateResponse(context["request"], name, context, status_code=status_code)
