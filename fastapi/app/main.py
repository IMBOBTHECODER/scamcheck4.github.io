"""Application entry point: creates and configures the FastAPI app.

Run from within this directory: `uvicorn main:app`
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from core.db import init_db
from routers import pages

# Keep the device cookie ~1 year so a device's history stays linked to it.
_SESSION_MAX_AGE = 60 * 60 * 24 * 365


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

# Signed-cookie session holds the device id (history key) + preferences.
app.add_middleware(
    SessionMiddleware, secret_key=settings.session_secret, max_age=_SESSION_MAX_AGE
)

# Static assets (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(pages.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}
