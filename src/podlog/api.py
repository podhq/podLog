"""Public API surface for podlog."""

from __future__ import annotations

import logging
from typing import Any, Dict

from .config.loader import load_configuration
from .core.manager import GLOBAL_MANAGER

_CONFIGURED = False


def configure(overrides: Dict[str, Any] | None = None) -> None:
    """Configure podlog using the provided overrides."""

    global _CONFIGURED
    config = load_configuration(overrides or {})
    GLOBAL_MANAGER.configure(config)
    _CONFIGURED = True


def _ensure_configured() -> None:
    global _CONFIGURED
    if not _CONFIGURED:
        configure({})


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name."""

    _ensure_configured()
    return GLOBAL_MANAGER.get_logger(name)


def get_context_logger(name: str, **context_kv: Any):
    """Return a context-aware logger carrying static key/value pairs."""

    _ensure_configured()
    return GLOBAL_MANAGER.get_context_logger(name, **context_kv)
