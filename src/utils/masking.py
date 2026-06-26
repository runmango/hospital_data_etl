"""Basic masking helpers for sensitive patient fields."""

from __future__ import annotations

import hashlib


def mask_name(name) -> str:
    if name is None:
        return ""
    value = str(name).strip()
    if not value:
        return ""
    if len(value) == 1:
        return "*"
    return value[0] + "*" * (len(value) - 1)


def hash_id_card(id_card, salt: str = "") -> str:
    if id_card is None:
        return ""
    value = str(id_card).strip()
    if not value:
        return ""
    payload = f"{salt}{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def mask_phone(phone) -> str:
    if phone is None:
        return ""
    value = str(phone).strip()
    if len(value) < 7:
        return "*" * len(value)
    return f"{value[:3]}****{value[-4:]}"
