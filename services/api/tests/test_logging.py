import logging

from app.core.logging import _ConsoleFormatter, get_logger


def test_structured_logger_handles_empty_and_populated_fields():
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    raw = logging.getLogger("test.structured")
    raw.handlers = [Capture()]
    raw.propagate = False
    raw.setLevel(logging.INFO)
    logger = get_logger("test.structured")
    logger.info("server_stopped")
    logger.info("run_started", run_id="run_1")

    formatter = _ConsoleFormatter()
    assert "server_stopped" in formatter.format(records[0])
    assert "run_id=run_1" in formatter.format(records[1])
