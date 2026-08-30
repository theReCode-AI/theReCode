import json
import logging

import pytest

from app.core.config import Settings
from app.core.logging import StructuredFormatter, TextFormatter, configure_logging


@pytest.fixture
def app_settings() -> Settings:
    return Settings(log_level="DEBUG", log_format="text", environment="test")


def test_configure_logging_text_format(app_settings: Settings) -> None:
    configure_logging(app_settings)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0].formatter, TextFormatter)


def test_configure_logging_json_format(app_settings: Settings) -> None:
    app_settings.log_format = "json"
    configure_logging(app_settings)

    formatter = logging.getLogger().handlers[0].formatter
    assert isinstance(formatter, StructuredFormatter)

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.run_id = "run-123"
    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "hello"
    assert payload["run_id"] == "run-123"
