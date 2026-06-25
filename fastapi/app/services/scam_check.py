"""Scam-check logic backed by the Gemini API.

Kept separate from the routes so the web layer stays thin: a route just calls
`check_message()` and renders whatever comes back.
"""
import itertools
import json
import logging
import re

from google import genai
from google.genai import types

from config import (
    OUTPUT_LANGUAGE_DIRECTIVE,
    RESCUE_OUTPUT_DIRECTIVE,
    RESCUE_PROMPT,
    SCAM_CHECK_PROMPT,
    settings,
)

logger = logging.getLogger("scamcheck.gemini")

# Fallback model if the caller doesn't pass one (per-user model overrides it).
MODEL_NAME = "gemini-2.5-flash"

# Cap input length: keeps latency/token cost bounded and blocks abuse.
MAX_MESSAGE_LENGTH = 2000

# Stable risk code -> display level (for CSS colour).
RISK_LEVELS = {"SAFE": 1, "WARNING": 2, "DANGER": 3}

# Fallback labels per language, used only if the model omits muc_do_rui_ro.
RISK_LABELS = {
    "vi": {"SAFE": "An toàn", "WARNING": "Cảnh báo", "DANGER": "Nguy hiểm"},
    "en": {"SAFE": "Safe", "WARNING": "Warning", "DANGER": "Danger"},
}


class ScamCheckError(Exception):
    """Raised when a message cannot be analyzed; message is user-safe."""


# One cached client per API key, plus a round-robin counter so successive
# requests start on different keys (spreads load across the pool's quotas).
_clients = {}
_rr = itertools.count()


def _client_for(api_key: str) -> genai.Client:
    """Return a cached Gemini client for `api_key`, building it on first use."""
    client = _clients.get(api_key)
    if client is None:
        client = genai.Client(api_key=api_key)
        _clients[api_key] = client
    return client


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

    # "Cô tâm lý" note: a gentle 2-3 sentence explanation of the manipulation
    # tactic. Optional — empty string if the model omits it.
    psych_note = str(data.get("loi_co_tam_ly", "")).strip()

    # Text the model read out of an uploaded image (empty for text input).
    extracted_text = str(data.get("van_ban_trich_xuat", "")).strip()

    return {
        "level": level,
        "label": label,
        "signals": signals,
        "actions": actions,
        "psych_note": psych_note,
        "extracted_text": extracted_text,
    }


def check_message(
    message: str,
    language: str = "vi",
    image_bytes: bytes = None,
    image_mime: str = None,
) -> dict:
    """Send `message` (and/or an image) to Gemini and return the parsed verdict.

    `language` ("vi"/"en") controls the language of the human-readable verdict
    text. `image_bytes`/`image_mime` carry an optional uploaded screenshot to
    analyze (the model reads its text). Raises ScamCheckError (with a user-safe
    message) on any failure.
    """
    # The prompt is the system instruction; the text to analyze goes in contents,
    # wrapped in <noi_dung> so the model treats it strictly as data. When only an
    # image is sent, the wrapper still tells the model where the data lives.
    text_block = message or "[Phân tích văn bản trong hình ảnh đính kèm]"
    parts = []
    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))
    parts.append(types.Part.from_text(text=f"<noi_dung>\n{text_block}\n</noi_dung>"))

    # Append the output-language directive so the verdict matches the UI language.
    directive = OUTPUT_LANGUAGE_DIRECTIVE.get(
        language, OUTPUT_LANGUAGE_DIRECTIVE["vi"]
    )
    system_instruction = f"{SCAM_CHECK_PROMPT}\n\n[NGÔN NGỮ TRẢ VỀ / OUTPUT LANGUAGE]\n{directive}"

    text = _complete(system_instruction, parts)
    try:
        return _parse(text, language)
    except json.JSONDecodeError as exc:
        raise ScamCheckError(
            "The analysis service returned an unreadable response."
        ) from exc


def _complete(system_instruction: str, content) -> str:
    """Run one JSON completion against the key pool, returning the raw text.

    Starts on a rotating key (round-robin) to spread load, then fails over to the
    next key on any error (quota / auth / network). Each key is tried at most
    once. Shared by the scam check and the rescue guidance.
    """
    cfg = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.1,
        response_mime_type="application/json",
    )

    pool = settings.gemini_key_pool
    if not pool:
        raise ScamCheckError("Scam checking is unavailable (server not configured).")

    start = next(_rr) % len(pool)
    ordered = pool[start:] + pool[:start]

    last_error = None
    for position, api_key in enumerate(ordered, start=1):
        try:
            response = _client_for(api_key).models.generate_content(
                model=MODEL_NAME, contents=content, config=cfg
            )
        except Exception as exc:  # quota / auth / network — try the next key
            last_error = exc
            logger.warning(
                "Gemini key %d/%d failed (%s) — trying next",
                position, len(pool), type(exc).__name__,
            )
            continue
        return response.text or ""

    # Every key in the pool failed (all over quota or invalid).
    logger.warning("All %d Gemini key(s) failed: %r", len(pool), last_error)
    raise ScamCheckError(
        "Unable to analyze the message right now. Please try again later."
    )


def _parse_rescue(text: str) -> dict:
    """Pull the 'Người ứng cứu' steps out of the model's JSON reply.

    Each step is a concrete action plus a sample sentence to read on the phone.
    """
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    if not match:
        raise ScamCheckError("The analysis service returned an unreadable response.")
    data = json.loads(match.group(0))

    raw_steps = data.get("cac_buoc", [])
    if not isinstance(raw_steps, list):
        raw_steps = []
    steps = []
    for item in raw_steps:
        if not isinstance(item, dict):
            continue
        action = str(item.get("hanh_dong", "")).strip()
        say = str(item.get("cau_noi_mau", "")).strip()
        if action:
            steps.append({"action": action, "say": say})

    return {"steps": steps}


def get_rescue_guidance(message: str, language: str = "vi") -> dict:
    """Emergency 'Người ứng cứu' guidance for someone who already acted on a scam.

    Returns {reassure, steps[], contacts[{name,phone,when}], note}. Raises
    ScamCheckError (user-safe) on failure. This is a SECOND Gemini call, made
    only on demand (when the user says they already sent money / shared info).
    """
    content = f"<noi_dung>\n{message}\n</noi_dung>"
    directive = RESCUE_OUTPUT_DIRECTIVE.get(language, RESCUE_OUTPUT_DIRECTIVE["vi"])
    system_instruction = f"{RESCUE_PROMPT}\n\n[NGÔN NGỮ TRẢ VỀ / OUTPUT LANGUAGE]\n{directive}"

    text = _complete(system_instruction, content)
    try:
        return _parse_rescue(text)
    except json.JSONDecodeError as exc:
        raise ScamCheckError(
            "The analysis service returned an unreadable response."
        ) from exc
