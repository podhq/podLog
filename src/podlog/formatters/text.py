"""Human readable text formatter with context awareness."""

from __future__ import annotations

import logging

__all__ = ["StructuredTextFormatter"]

_DEFAULT_FMT = "%(asctime)s | %(levelname)-5s | %(name)s | %(context)s | %(message)s"
_DEFAULT_FMT_WITH_EXTRAS = "%(asctime)s | %(levelname)-5s | %(name)s | %(context)s | %(message)s | %(extra_kvs)s"


class StructuredTextFormatter(logging.Formatter):
    """Formatter that ensures context/extra fields are displayed."""

    def __init__(self, *, show_extras: bool = False, fmt: str | None = None, datefmt: str | None = "%Y-%m-%d %H:%M:%S") -> None:
        final_fmt = fmt or (_DEFAULT_FMT_WITH_EXTRAS if show_extras else _DEFAULT_FMT)
        super().__init__(final_fmt, datefmt=datefmt)
        self.show_extras = show_extras

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        record.__dict__.setdefault("context", "-")
        if self.show_extras:
            record.__dict__.setdefault("extra_kvs", "-")
        else:
            record.__dict__.setdefault("extra_kvs", "")
        return super().format(record)
