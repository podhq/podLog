"""Console handler helpers."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Any

__all__ = ["ConsoleHandlerConfig", "build_console_handler"]


@dataclass(slots=True)
class ConsoleHandlerConfig:
    """Configuration for console handlers."""

    stream: str = "stderr"
    level: int = logging.INFO


def build_console_handler(config: ConsoleHandlerConfig | None = None) -> logging.Handler:
    """Construct a :class:`logging.StreamHandler` based on ``config``."""

    cfg = config or ConsoleHandlerConfig()
    stream: Any
    if cfg.stream == "stdout":
        stream = sys.stdout
    elif cfg.stream == "stderr":
        stream = sys.stderr
    else:
        stream = None
    handler = logging.StreamHandler(stream=stream)
    handler.setLevel(cfg.level)
    return handler
