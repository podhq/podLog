"""Null handler utilities."""

from __future__ import annotations

import logging

__all__ = ["build_null_handler"]


def build_null_handler() -> logging.Handler:
    """Return a ``NullHandler``."""

    return logging.NullHandler()
