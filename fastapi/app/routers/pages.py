"""HTML page routes (server-rendered via Jinja2)."""
import json
import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import APP_VERSION, AVAILABLE_LANGUAGES
from core import i18n, prefs
from core.db import get_db
from core.device import get_device_id
from models import Scan
from services.scam_check import MAX_MESSAGE_LENGTH, ScamCheckError, check_message

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("scamcheck.pages")


def _ctx(request: Request, title: str, **extra) -> dict:
    """Base context — theme/language come from this device's preferences."""
    p = prefs.get_prefs(request)
    context = {
        "request": request,
        "title": title,
        "t": i18n.strings(p["language"]),
        "theme": p["theme"],
        "language": p["language"],
    }
    context.update(extra)
    return context


def _scan_view(scan: Scan) -> dict:
    return {
        "level": scan.level,
        "label": scan.label,
        "message": scan.message,
        "signals": json.loads(scan.signals_json or "[]"),
        "actions": json.loads(scan.actions_json or "[]"),
        "created_at": scan.created_at,
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html", _ctx(request, "Home", max_length=MAX_MESSAGE_LENGTH)
    )


@router.post("/", response_class=HTMLResponse)
def check(request: Request, text: str = Form(""), db: Session = Depends(get_db)):
    text = text.strip()
    context = _ctx(request, "Home", submitted=text, max_length=MAX_MESSAGE_LENGTH)
    t = context["t"]

    if not text:
        context["error"] = t["err_empty"]
    elif len(text) > MAX_MESSAGE_LENGTH:
        context["error"] = t["err_too_long"].format(max=MAX_MESSAGE_LENGTH)
    else:
        try:
            result = check_message(text, language=context["language"])
            context["result"] = result
        except ScamCheckError as exc:
            context["error"] = str(exc)
        else:
            # Persisting to history is best-effort: if the DB is down, the user
            # still sees their result — only the history record is skipped.
            try:
                db.add(
                    Scan(
                        device_id=get_device_id(request),
                        message=text,
                        level=result["level"],
                        label=result["label"],
                        signals_json=json.dumps(result["signals"], ensure_ascii=False),
                        actions_json=json.dumps(result["actions"], ensure_ascii=False),
                    )
                )
                db.commit()
            except SQLAlchemyError as exc:
                db.rollback()
                logger.warning("scan not saved to history — database unavailable: %s", exc)

    return templates.TemplateResponse("index.html", context)


@router.get("/history", response_class=HTMLResponse)
def history(request: Request, db: Session = Depends(get_db)):
    device_id = get_device_id(request)
    try:
        scans = (
            db.query(Scan)
            .filter(Scan.device_id == device_id)
            .order_by(desc(Scan.created_at))
            .limit(10)
            .all()
        )
        views = [_scan_view(s) for s in scans]
        db_error = False
    except SQLAlchemyError as exc:
        # DB down: show the page with an "unavailable" notice instead of a 500.
        logger.warning("history query failed — database unavailable: %s", exc)
        views, db_error = [], True
    return templates.TemplateResponse(
        "history.html",
        _ctx(request, "History", scans=views, db_error=db_error),
    )


@router.post("/history/clear")
def clear_history(request: Request, db: Session = Depends(get_db)):
    try:
        db.query(Scan).filter(Scan.device_id == get_device_id(request)).delete()
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("clear history failed — database unavailable: %s", exc)
    return RedirectResponse("/history", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, saved: bool = False):
    return templates.TemplateResponse(
        "settings.html",
        _ctx(
            request,
            "Settings",
            saved=saved,
            app_version=APP_VERSION,
            available_languages=AVAILABLE_LANGUAGES,
            max_length=MAX_MESSAGE_LENGTH,
        ),
    )


@router.post("/settings")
def save_settings(
    request: Request,
    theme: str = Form(...),
    language: str = Form(...),
):
    prefs.set_prefs(request, theme=theme, language=language)
    return RedirectResponse("/settings?saved=1", status_code=303)
