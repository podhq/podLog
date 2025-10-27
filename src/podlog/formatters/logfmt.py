"""logfmt formatter implementation."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

__all__ = ["LogFmtFormatter"]


def _escape(value: Any) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or "=" in text or "\"" in text:
        escaped = text.replace("\"", "\\\"")
        return f'"{escaped}"'
    return text


class LogFmtFormatter(logging.Formatter):
    """Render records into logfmt (key=value) form."""

    def __init__(self, *, keys: Iterable[str] | None = None, datefmt: str | None = "%Y-%m-%dT%H:%M:%S%z") -> None:
        super().__init__(datefmt=datefmt)
        self.extra_keys = list(keys or [])

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        parts = [
            f"ts={_escape(self.formatTime(record, self.datefmt))}",
            f"level={_escape(record.levelname)}",
            f"logger={_escape(record.name)}",
            f"msg={_escape(record.getMessage())}",
        ]
        context = getattr(record, "context", None)
        if context:
            parts.append(f"context={_escape(context)}")

        data: Mapping[str, Any] = record.__dict__
        extra_keys = self.extra_keys or [
            key
            for key in data.keys()
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "asctime",
                "context",
                "extra_kvs",
            }
        ]

        for key in extra_keys:
            if key in data:
                parts.append(f"{key}={_escape(data[key])}")

        if record.exc_info:
            parts.append(f"exc={_escape(self.formatException(record.exc_info))}")

        return " ".join(parts)
