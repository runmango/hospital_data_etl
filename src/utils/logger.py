"""Logging setup with automatic sensitive value redaction."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .secret_redactor import redact_text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = redact_text(message)
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
