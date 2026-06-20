"""HTML page routes (server-rendered via Jinja2)."""
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
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


def _highlight(message: str, signals: list) -> Markup:
    """Return the message as HTML with each flagged snippet wrapped in <mark>.

    Every character of the original text is HTML-escaped; only the <mark> tags
    we insert are live HTML, so this is safe from XSS. Snippets come from the
    model's `doan_trich` fields; matching is case-insensitive and best-effort
    (a snippet the model paraphrased simply won't highlight).
    """
    # Ignore degenerate 1–2 char snippets: a short/common needle (or one a user
    # steered the model into emitting) would otherwise highlight half the text.
    snippets = [
        s.get("doan_trich", "").strip()
        for s in signals
        if isinstance(s, dict) and len(s.get("doan_trich", "").strip()) >= 3
    ]
    if not snippets:
        return escape(message)

    # Collect every match span, then merge overlaps so nesting can't happen.
    lowered = message.lower()
    spans = []
    for snip in snippets:
        needle = snip.lower()
        start = 0
        while (idx := lowered.find(needle, start)) != -1:
            spans.append((idx, idx + len(snip)))
            start = idx + len(snip)
    if not spans:
        return escape(message)

    spans.sort()
    merged = [spans[0]]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Rebuild, escaping each segment; wrap the flagged ranges in <mark>.
    out, cursor = [], 0
    for s, e in merged:
        out.append(escape(message[cursor:s]))
        out.append(Markup('<mark class="flag">'))
        out.append(escape(message[s:e]))
        out.append(Markup("</mark>"))
        cursor = e
    out.append(escape(message[cursor:]))
    return Markup("").join(out)


def _scan_view(scan: Scan) -> dict:
    signals = json.loads(scan.signals_json or "[]")
    return {
        "id": scan.id,
        "level": scan.level,
        "label": scan.label,
        "message": scan.message,
        "message_html": _highlight(scan.message, signals),
        "signals": signals,
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
            started = time.perf_counter()
            result = check_message(text, language=context["language"])
            elapsed_ms = int((time.perf_counter() - started) * 1000)
        except ScamCheckError as exc:
            context["error"] = str(exc)
        else:
            scan = Scan(
                device_id=get_device_id(request),
                message=text,
                level=result["level"],
                label=result["label"],
                signals_json=json.dumps(result["signals"], ensure_ascii=False),
                actions_json=json.dumps(result["actions"], ensure_ascii=False),
            )
            try:
                db.add(scan)
                db.commit()
                db.refresh(scan)  # populate scan.id
                # Post/Redirect/Get: show the result on its own page so a refresh
                # doesn't re-submit the form. Pass the analysis time along.
                return RedirectResponse(f"/result/{scan.id}?ms={elapsed_ms}", status_code=303)
            except SQLAlchemyError as exc:
                db.rollback()
                logger.warning("scan not saved — database unavailable: %s", exc)
                # No id to link to, so fall back to showing the result inline.
                context["result"] = result

    return templates.TemplateResponse("index.html", context)


@router.get("/result/{scan_id}", response_class=HTMLResponse)
def result_page(
    request: Request,
    scan_id: int,
    ms: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Dedicated page for one scan's result (reached via redirect after a check).

    `ms` is the analysis time carried over from the check redirect; it is only
    shown right after a check (revisiting from history has no `ms`).
    """
    device_id = get_device_id(request)
    try:
        # Scope by device_id so a device can only see its own results.
        scan = (
            db.query(Scan)
            .filter(Scan.id == scan_id, Scan.device_id == device_id)
            .first()
        )
    except SQLAlchemyError as exc:
        logger.warning("result lookup failed — database unavailable: %s", exc)
        scan = None

    if scan is None:
        # Unknown id, not this device's, or DB down → back to the checker.
        return RedirectResponse("/", status_code=303)

    # Ignore a missing or obviously bogus (spoofed) value — display only.
    took_ms = ms if (ms is not None and 0 <= ms <= 600000) else None

    return templates.TemplateResponse(
        "result.html", _ctx(request, "Result", result=_scan_view(scan), took_ms=took_ms)
    )


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
