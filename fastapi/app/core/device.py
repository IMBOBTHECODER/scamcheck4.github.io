"""Anonymous per-device identity, stored in the signed session cookie.

Not an account — just a stable random id so a device's scan history can be
keyed in the database. The cookie is long-lived (see SessionMiddleware max_age).
"""
import uuid


def get_device_id(request) -> str:
    """Return this device's id, creating and storing one on first use."""
    device_id = request.session.get("device_id")
    if not device_id:
        device_id = uuid.uuid4().hex
        request.session["device_id"] = device_id
    return device_id
