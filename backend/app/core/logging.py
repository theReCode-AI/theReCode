import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

STANDARD_LOG_RECORD_ATTRS = frozenset(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__.keys()
)


class StructuredFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_ATTRS:
                payload[key] = value

        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )


def configure_logging(app_settings: Settings) -> None:
    """Configure application-wide structured logging."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(app_settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    if app_settings.log_format == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger("app").setLevel(app_settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
