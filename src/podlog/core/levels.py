"""Custom log level helpers."""

from __future__ import annotations

import logging
from typing import Any, Callable

TRACE_LEVEL_NAME = "TRACE"
TRACE_LEVEL_NUM = 5


def register_trace_level(enable: bool = True) -> None:
    """Register the TRACE level on the stdlib logging module.

    When ``enable`` is ``False`` the function becomes a no-op. The level is
    installed only once even if called repeatedly.
    """

    if not enable:
        return

    if logging.getLevelName(TRACE_LEVEL_NUM) != TRACE_LEVEL_NAME:
        logging.addLevelName(TRACE_LEVEL_NUM, TRACE_LEVEL_NAME)
    if not hasattr(logging, TRACE_LEVEL_NAME):
        setattr(logging, TRACE_LEVEL_NAME, TRACE_LEVEL_NUM)

    if not hasattr(logging.Logger, "trace"):
        def trace(self: logging.Logger, message: str, *args: object, **kwargs: Any) -> None:  # type: ignore[override]
            if self.isEnabledFor(TRACE_LEVEL_NUM):
                self._log(TRACE_LEVEL_NUM, message, args, **kwargs)

        logging.Logger.trace = trace  # type: ignore[assignment]


def get_level_by_name(name: str) -> int:
    """Resolve a logging level from a friendly name."""

    if name.upper() == TRACE_LEVEL_NAME:
        return TRACE_LEVEL_NUM
    if name.isdigit():
        return int(name)
    resolved = logging.getLevelName(name.upper())
    if isinstance(resolved, int):
        return resolved
    return logging.INFO


def ensure_level(value: int | str) -> int:
    """Normalize user supplied level values."""

    if isinstance(value, int):
        return value
    return get_level_by_name(value)


def level_filter(level: int) -> Callable[[logging.LogRecord], bool]:
    """Return a predicate that checks for a specific level."""

    def predicate(record: logging.LogRecord) -> bool:
        return record.levelno == level

    return predicate
