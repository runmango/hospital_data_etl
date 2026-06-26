"""Security helpers used by CLI and scripts."""

from __future__ import annotations

from .secret_redactor import redact_mapping, redact_text, short_sha256


def safe_error_message(exc: Exception) -> str:
    return redact_text(str(exc))


def safe_summary(data: dict) -> dict:
    return redact_mapping(data)


def password_digest(password: str) -> str:
    return short_sha256(password) if password else ""
