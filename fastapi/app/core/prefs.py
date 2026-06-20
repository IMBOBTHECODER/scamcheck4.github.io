"""Per-device preferences, stored in the signed session cookie.

No accounts and no database: each browser keeps its own theme/language in its
session cookie. Reads validate against the allowed sets and fall back to
defaults, so a tampered cookie can never inject bad values.
"""
from config import AVAILABLE_LANGUAGES, AVAILABLE_THEMES, DEFAULT_PREFERENCES

_ALLOWED = {
    "theme": AVAILABLE_THEMES,
    "language": AVAILABLE_LANGUAGES,
}


def get_prefs(request) -> dict:
    """Current device preferences (defaults for anything missing/invalid)."""
    stored = request.session.get("prefs") or {}
    prefs = dict(DEFAULT_PREFERENCES)
    for key, allowed in _ALLOWED.items():
        if stored.get(key) in allowed:
            prefs[key] = stored[key]
    return prefs


def set_prefs(request, **values) -> dict:
    """Validate, merge into the current prefs, and persist to the session."""
    prefs = get_prefs(request)
    for key, allowed in _ALLOWED.items():
        if values.get(key) in allowed:
            prefs[key] = values[key]
    request.session["prefs"] = prefs
    return prefs
