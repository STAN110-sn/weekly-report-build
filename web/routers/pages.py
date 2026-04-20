"""
HTML ページルーター
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from ..auth import _extract_token, decode_jwt, _member_from_payload
from ..database import get_db
from ..models import Member

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _get_user_for_page(request: Request, db: Session) -> Member | None:
    from config import config as _cfg
    if _cfg.DEV_BYPASS_AUTH:
        from ..auth import _dev_member
        return _dev_member()
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_jwt(token)
    if not payload:
        return None
    return _member_from_payload(payload, db)


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    user = _get_user_for_page(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/members", status_code=302)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/members", response_class=HTMLResponse)
def members_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_for_page(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        "members.html",
        {"request": request, "user": user, "is_admin": user.role == "admin"},
    )


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_for_page(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "user": user, "is_admin": user.role in ("admin", "executive")},
    )


@router.get("/weekly-report", response_class=HTMLResponse)
def weekly_report_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_for_page(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        "weekly_report.html",
        {"request": request, "user": user},
    )
