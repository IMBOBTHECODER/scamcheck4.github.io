"""Application entry point: creates and configures the FastAPI app.

Run from within this directory: `uvicorn main:app`
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse

from config import settings
from core.db import init_db
from routers import pages

logger = logging.getLogger("scamcheck.main")

# Keep the device cookie ~1 year so a device's history stays linked to it.
_SESSION_MAX_AGE = 60 * 60 * 24 * 365

# Sent on every response. Defence-in-depth against clickjacking, MIME-sniffing,
# and injected content. The CSP allowlists only what the pages actually use
# (self, Google Fonts, and the inline form script); everything else is blocked.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    ),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warn loudly if the cookie-signing secret was left at its insecure default
    # (forged session cookies would otherwise be possible).
    if settings.session_secret == "dev-insecure-change-me":
        logger.warning("SESSION_SECRET is the insecure default — set a real secret in .env")
    # Best-effort table bootstrap. init_db() never raises on a DB outage — it
    # logs and returns False — so the site still boots and serves pages that
    # don't need the database (home, settings). History degrades gracefully.
    init_db()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)


@app.middleware("http")
async def harden_request(request: Request, call_next):
    """Reject oversized bodies early, then add security headers to the response."""
    # Block oversized payloads before they are read into memory (basic DoS guard).
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.max_request_bytes:
                return PlainTextResponse("Payload too large", status_code=413)
        except ValueError:
            return PlainTextResponse("Bad Content-Length", status_code=400)

    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


# Signed-cookie session holds the device id (history key) + preferences.
# same_site="lax" keeps the cookie off cross-site POSTs (CSRF mitigation);
# https_only marks it Secure in production.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=_SESSION_MAX_AGE,
    same_site="lax",
    https_only=settings.session_https_only,
)

# Static assets (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(pages.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}
