"""JSON Lines formatter."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, MutableMapping

__all__ = ["JSONLinesFormatter"]

_STANDARD_ATTRS = {
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


class JSONLinesFormatter(logging.Formatter):
    """Emit structured records as one JSON object per line."""

    def __init__(
        self,
        *,
        whitelist: Iterable[str] | None = None,
        drop_fields: Iterable[str] | None = None,
        datefmt: str | None = "%Y-%m-%dT%H:%M:%S%z",
    ) -> None:
        super().__init__(datefmt=datefmt)
        self.whitelist = list(whitelist or [])
        self.drop_fields = set(drop_fields or [])

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: MutableMapping[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "context"):
            payload["context"] = getattr(record, "context")

        extra: dict[str, Any]
        data = record.__dict__
        if self.whitelist:
            extra = {key: data[key] for key in self.whitelist if key in data}
        else:
            extra = {
                key: value
                for key, value in data.items()
                if key not in _STANDARD_ATTRS and key not in self.drop_fields
            }

        if extra:
            payload["extra"] = extra

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
