"""Utilities for redacting secrets before display, logging, or export."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "access_key",
    "private_key",
    "api_key",
    "authorization",
)

_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:PASSWORD|PASSWD|PWD|TOKEN|SECRET|ACCESS_KEY|PRIVATE_KEY|API_KEY)[A-Z0-9_]*\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_AUTH_RE = re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._~+/=-]+")
_ORACLE_SLASH_RE = re.compile(r"(?i)\b([A-Za-z0-9_$#.-]+)/(?!/)([^\s/@:]+)@([A-Za-z0-9_.-]+(?::\d+)?(?:/[A-Za-z0-9_$#.-]+)?)")
_ORACLE_URL_RE = re.compile(r"(?i)\b((?:oracle|oracledb)://[^:\s/@]+:)([^\s/@]+)(@[^\s]+)")


def redact_secret(value: str) -> str:
    if value is None:
        return ""
    return "" if str(value) == "" else "<redacted>"


def short_sha256(value: str, length: int = 12) -> str:
    if value is None:
        value = ""
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:length]}"


def is_sensitive_key(key: str) -> bool:
    normalized = str(key).lower()
    if normalized.endswith(("_set", "_digest", "_env")) or normalized in {"password_set", "password_digest"}:
        return False
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def redact_text(text: str) -> str:
    if text is None:
        return ""
    redacted = str(text)
    redacted = _AUTH_RE.sub(r"\1<redacted>", redacted)

    def _assignment_replacement(match: re.Match) -> str:
        key = match.group(1).split("=")[0].split(":")[0].strip().lower()
        if key.endswith(("_set", "_digest", "_env")) or key in {"password_set", "password_digest"}:
            return match.group(0)
        return f"{match.group(1)}<redacted>"

    redacted = _ASSIGNMENT_RE.sub(_assignment_replacement, redacted)
    redacted = _ORACLE_URL_RE.sub(lambda match: f"{match.group(1)}<redacted>{match.group(3)}", redacted)
    redacted = _ORACLE_SLASH_RE.sub(lambda match: f"{match.group(1)}/<redacted>@{match.group(3)}", redacted)
    return redacted


def redact_mapping(data: Any) -> Any:
    if isinstance(data, dict):
        safe = {}
        for key, value in data.items():
            if is_sensitive_key(str(key)):
                safe[key] = redact_secret(str(value)) if value not in (None, "") else ""
            else:
                safe[key] = redact_mapping(value)
        return safe
    if isinstance(data, list):
        return [redact_mapping(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact_mapping(item) for item in data)
    if isinstance(data, str):
        return redact_text(data)
    return copy.deepcopy(data)

