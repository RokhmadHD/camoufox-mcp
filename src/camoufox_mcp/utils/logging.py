"""
Structured logging for Camoufox MCP.

Supports two output modes:
  - plain text  (default, human-friendly)
  - JSON        (CAMOUFOX_LOG_JSON=true, machine-friendly for log aggregators)

Usage:
    from camoufox_mcp.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("page loaded", extra={"session_id": sid, "url": url, "duration_ms": 320})
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

# --------------------------------------------------------------------------- #
# JSON formatter
# --------------------------------------------------------------------------- #


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    # Fields we want to exclude from the 'extra' payload
    _SKIP = frozenset(
        {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "message",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        # Attach any extra fields passed via logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in self._SKIP:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Plain-text formatter  (matches the spec from the architecture doc)
# --------------------------------------------------------------------------- #
# Example output:
#   [INFO]  session=abc tool=browser_open url=https://example.com duration=1240ms


class _PlainFormatter(logging.Formatter):
    DATEFMT = "%H:%M:%S"

    _LEVEL_COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def __init__(self, colorize: bool = True) -> None:
        super().__init__()
        self._colorize = colorize and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        record.message = record.getMessage()
        ts = time.strftime(self.DATEFMT, time.localtime(record.created))
        level = record.levelname

        if self._colorize:
            color = self._LEVEL_COLORS.get(level, "")
            level_str = f"{color}[{level}]{self._RESET}"
        else:
            level_str = f"[{level}]"

        # Collect known extra fields for inline display
        extras = _extract_log_extras(record)
        extras_str = "  " + "  ".join(f"{k}={v}" for k, v in extras.items()) if extras else ""

        line = f"{ts} {level_str} {record.message}{extras_str}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #

_STANDARD_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
}


def _extract_log_extras(record: logging.LogRecord) -> dict[str, Any]:
    """Return extra key=value pairs that were attached to the log record."""
    return {k: v for k, v in record.__dict__.items() if k not in _STANDARD_FIELDS}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

_initialized = False


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """
    Configure the root logger for the application.

    Call this once at startup (in server.py or __main__.py).
    Subsequent calls are no-ops.
    """
    global _initialized
    if _initialized:
        return

    root = logging.getLogger("camoufox_mcp")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if json_logs:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_PlainFormatter())

    root.addHandler(handler)
    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'camoufox_mcp' namespace.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A ``logging.Logger`` instance.
    """
    # Normalise so callers can pass either the full dotted name or a short name
    if not name.startswith("camoufox_mcp"):
        name = f"camoufox_mcp.{name}"
    return logging.getLogger(name)
