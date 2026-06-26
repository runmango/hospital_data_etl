"""Input validators for CLI parameters."""

from __future__ import annotations

from datetime import datetime


def validate_yyyymmdd(value: str) -> str:
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"Date must use YYYYMMDD format, got: {value}") from exc
    return value


def validate_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    start = validate_yyyymmdd(start_date)
    end = validate_yyyymmdd(end_date)
    if start > end:
        raise ValueError(f"start_date must be earlier than or equal to end_date: {start} > {end}")
    return start, end

