"""Structured logging setup for paperboy.

Replaces ad-hoc `print(..., file=sys.stderr)` with standard-library
logging.  In container / production mode JSON formatting is available
via the PAPERBOY_LOG_FORMAT=json env var.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


class _JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # merge extra fields
        for key in ("event", "source", "actor", "stream", "dry_run", "elapsed_ms", "method", "path", "status", "job", "ok"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str | None = None, force_json: bool | None = None) -> None:
    """Set up root logging for the paperboy package.

    Args:
        level: One of DEBUG/INFO/WARNING/ERROR/CRITICAL.  Defaults to the
               PAPERBOY_LOG_LEVEL env var, then INFO.
        force_json: True to force JSON output.  Defaults to truthy
                    PAPERBOY_LOG_FORMAT=json env var.
    """
    lvl = (level or os.environ.get("PAPERBOY_LOG_LEVEL", "INFO")).upper()
    json_mode = force_json if force_json is not None else os.environ.get("PAPERBOY_LOG_FORMAT", "").lower() == "json"

    root = logging.getLogger("paperboy")
    root.setLevel(getattr(logging, lvl, logging.INFO))

    # Clear existing handlers so re-calls are idempotent
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    if json_mode:
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
    root.addHandler(handler)

    # Also quiet noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the paperboy namespace."""
    return logging.getLogger(f"paperboy.{name}")
