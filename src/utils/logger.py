"""Logging setup with simple sensitive value filtering."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path


class SensitiveDataFilter(logging.Filter):
    _patterns = [
        re.compile(r"(?i)(password\s*[=:]\s*)[^\s,;]+"),
        re.compile(r"(?i)(pwd\s*[=:]\s*)[^\s,;]+"),
        re.compile(r"(?i)([A-Z0-9_]*PASSWORD\s*[=:]\s*)[^\s,;]+"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\1******", message)
        record.msg = message
        record.args = ()
        return True


def setup_logger(log_dir: str | Path, name: str = "hospital_data_etl") -> logging.Logger:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    log_file = path / f"etl_{datetime.now().strftime('%Y%m%d')}.log"
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sensitive_filter = SensitiveDataFilter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(sensitive_filter)
    logger.addHandler(stream_handler)

    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("File logging disabled because log file is not writable: %s", exc)

    return logger
