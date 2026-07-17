"""Structured logging with JSON output for production and colored console for dev.

Usage::

    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("agent_reply", agent_id=agent["id"], provider="hermes")

The ``extra`` keyword dict is automatically serialized as JSON in the log
record so downstream tools (ELK, Datadog, etc.) can parse structured fields.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any


class _JsonFormatter(logging.Formatter):
    """JSON Lines formatter — one record per line, machine-parseable."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(UTC).isoformat()
        base: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge structured extras (e.g. logger.info("msg", agent_id="x"))
        if isinstance(record.args, dict):
            base.update(record.args)
        if record.exc_info and record.exc_info[1]:
            base["exc"] = str(record.exc_info[1])
        return json.dumps(base, default=str, ensure_ascii=False)


class _ConsoleFormatter(logging.Formatter):
    """Human-readable formatter with dimmed logger name and coloured level."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:<8}{self.RESET}"
        logger_name = f"{self.DIM}{record.name}{self.RESET}"
        msg = record.getMessage()
        # Append structured extras inline
        if isinstance(record.args, dict):
            extras = " ".join(
                f"{k}={v}" for k, v in record.args.items() if k != "exc"
            )
            if extras:
                msg = f"{msg}  {self.DIM}{extras}{self.RESET}"
        return f"{level} {logger_name}  {msg}"


def setup_logging(*, json_output: bool = False) -> None:
    """Configure the root logger once at startup."""
    level = os.environ.get("AGENTPULSE_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        _JsonFormatter() if json_output else _ConsoleFormatter()
    )
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    # Clear any existing handlers to avoid duplicates
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that supports ``logger.info("msg", key=val, ...)``.

    Structured fields passed as keyword arguments are merged into the log
    record via a custom ``logging.LoggerAdapter``-style approach.
    """
    return _StructuredAdapter(logging.getLogger(name))


class _StructuredAdapter:
    """Wraps a standard logger so ``logger.info("msg", k=v)`` works."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def debug(self, msg: str, **extra: Any) -> None:
        self._logger.debug(msg, extra)

    def info(self, msg: str, **extra: Any) -> None:
        self._logger.info(msg, extra)

    def warning(self, msg: str, **extra: Any) -> None:
        self._logger.warning(msg, extra)

    def error(self, msg: str, **extra: Any) -> None:
        self._logger.error(msg, extra)

    def exception(self, msg: str, **extra: Any) -> None:
        self._logger.exception(msg, extra)

    def critical(self, msg: str, **extra: Any) -> None:
        self._logger.critical(msg, extra)
