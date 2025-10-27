"""Syslog handler helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from logging.handlers import SysLogHandler
from pathlib import Path
from typing import Tuple

__all__ = ["SyslogConfig", "build_syslog_handler"]


@dataclass(slots=True)
class SyslogConfig:
    """Configuration for syslog handler."""

    address: str | Tuple[str, int] | None = ("localhost", 514)
    facility: int = SysLogHandler.LOG_USER
    socktype: int | None = None


def _parse_address(address: str | Tuple[str, int] | None) -> str | Tuple[str, int] | Path | None:
    if address is None:
        return None
    if isinstance(address, tuple):
        return address
    if address.startswith("unix://"):
        return Path(address.removeprefix("unix://"))
    if address.startswith("udp://") or address.startswith("tcp://"):
        _, rest = address.split("://", 1)
        host, _, port_str = rest.partition(":")
        port = int(port_str or "514")
        return (host or "localhost", port)
    return address


def build_syslog_handler(config: SyslogConfig | None = None) -> logging.Handler:
    cfg = config or SyslogConfig()
    address = _parse_address(cfg.address)
    handler = SysLogHandler(address=address, facility=cfg.facility, socktype=cfg.socktype)
    return handler
