"""GELF UDP handler implementation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from logging.handlers import DatagramHandler
from typing import Mapping

__all__ = ["GELFUDPConfig", "GELFUDPHandler", "build_gelf_udp_handler"]

_GELF_VERSION = "1.1"


@dataclass(slots=True)
class GELFUDPConfig:
    host: str = "localhost"
    port: int = 12201


class GELFUDPHandler(DatagramHandler):
    """Minimal GELF handler sending JSON payloads over UDP."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(host, port)

    def makePickle(self, record: logging.LogRecord) -> bytes:  # type: ignore[override]
        payload = {
            "version": _GELF_VERSION,
            "host": record.name,
            "short_message": record.getMessage(),
            "timestamp": record.created,
            "level": record.levelno,
        }
        if record.exc_info:
            formatter = self.formatter or logging.Formatter()
            payload["full_message"] = formatter.formatException(record.exc_info)
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in {"name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process", "asctime"}
        }
        for key, value in extra.items():
            payload[f"_{key}"] = value
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return data


def build_gelf_udp_handler(config: GELFUDPConfig | None = None) -> logging.Handler:
    cfg = config or GELFUDPConfig()
    return GELFUDPHandler(cfg.host, cfg.port)
