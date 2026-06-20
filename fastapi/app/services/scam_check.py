"""Scam-check logic backed by the Gemini API.

Kept separate from the routes so the web layer stays thin: a route just calls
`check_message()` and renders whatever comes back.
"""
import json
import re
from typing import Optional

from google import genai
from google.genai import types

from config import OUTPUT_LANGUAGE_DIRECTIVE, SCAM_CHECK_PROMPT, settings

# Fallback model if the caller doesn't pass one (per-user model overrides it).
MODEL_NAME = "gemini-2.5-flash"

# Cap input length: keeps latency/token cost bounded and blocks abuse.
MAX_MESSAGE_LENGTH = 4000

# Stable risk code -> display level (for CSS colour).
RISK_LEVELS = {"SAFE": 1, "WARNING": 2, "DANGER": 3}

# Fallback labels per language, used only if the model omits muc_do_rui_ro.
RISK_LABELS = {
    "vi": {"SAFE": "An toàn", "WARNING": "Cảnh báo", "DANGER": "Nguy hiểm"},
    "en": {"SAFE": "Safe", "WARNING": "Warning", "DANGER": "Danger"},
}


class ScamCheckError(Exception):
    """Raised when a message cannot be analyzed; message is user-safe."""


_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    """Lazily build a single shared Gemini client."""
    global _client
    if not settings.gemini_api_key:
        raise ScamCheckError("Scam checking is unavailable (server not configured).")
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _parse(text: str, language: str = "vi") -> dict:
    """Pull a validated verdict out of the model's (already JSON) reply."""
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    if not match:
        raise ScamCheckError("The analysis service returned an unreadable response.")

    data = json.loads(match.group(0))

    # Stable code drives the UI; default to WARNING when unclear (err on caution).
    code = str(data.get("muc_do", "")).strip().upper()
    if code not in RISK_LEVELS:
        code = "WARNING"
    level = RISK_LEVELS[code]
    labels = RISK_LABELS.get(language, RISK_LABELS["vi"])
    label = str(data.get("muc_do_rui_ro", "")).strip() or labels[code]

    raw_signals = data.get("danh_sach_dau_hieu", [])
    if not isinstance(raw_signals, list):
        raw_signals = []
    signals = []
    for item in raw_signals:
        if not isinstance(item, dict):
            continue
        dau_hieu = str(item.get("dau_hieu", "")).strip()
        doan_trich = str(item.get("doan_trich", "")).strip()
        if dau_hieu or doan_trich:
            signals.append({"dau_hieu": dau_hieu, "doan_trich": doan_trich})

    raw_actions = data.get("hanh_dong_de_xuat", [])
    if not isinstance(raw_actions, list):
        raw_actions = []
    actions = [str(a).strip() for a in raw_actions if str(a).strip()]

    return {
        "level": level,
        "label": label,
        "signals": signals,
        "actions": actions,
    }


def check_message(message: str, language: str = "vi") -> dict:
    """Send `message` to Gemini and return {level, label, signals, actions}.

    `language` ("vi"/"en") controls the language of the human-readable verdict
    text. Raises ScamCheckError (with a user-safe message) on any failure.
    """
    # The prompt is the system instruction; the text to analyze goes in contents,
    # wrapped in <noi_dung> so the model treats it strictly as data.
    content = f"<noi_dung>\n{message}\n</noi_dung>"

    # Append the output-language directive so the verdict matches the UI language.
    directive = OUTPUT_LANGUAGE_DIRECTIVE.get(
        language, OUTPUT_LANGUAGE_DIRECTIVE["vi"]
    )
    system_instruction = f"{SCAM_CHECK_PROMPT}\n\n[NGÔN NGỮ TRẢ VỀ / OUTPUT LANGUAGE]\n{directive}"

    try:
        response = _get_client().models.generate_content(
            model=MODEL_NAME,
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
    except ScamCheckError:
        raise
    except Exception as exc:  # network / quota / API errors
        raise ScamCheckError(
            "Unable to analyze the message right now. Please try again later."
        ) from exc

    try:
        return _parse(response.text or "", language)
    except json.JSONDecodeError as exc:
        raise ScamCheckError(
            "The analysis service returned an unreadable response."
        ) from exc
