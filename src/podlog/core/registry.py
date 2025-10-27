"""Registry of formatter, handler, and filter builders."""

from __future__ import annotations

import logging
import logging.handlers
from socket import SocketKind
from typing import Any, Callable, Dict, Iterable

from ..config.schema import FilterSpec, FormatterSpec, HandlerSpec, PathsConfig
from ..formatters.csvfmt import CSVFormatter
from ..formatters.jsonl import JSONLinesFormatter
from ..formatters.logfmt import LogFmtFormatter
from ..formatters.text import StructuredTextFormatter
from ..handlers.console import ConsoleHandlerConfig, build_console_handler
from ..handlers.file_rotating import (
    FileHandlerConfig,
    RetentionPolicy,
    SizeRotation,
    TimeRotation,
    build_file_handler,
)
from ..handlers.gelf_udp import GELFUDPConfig, build_gelf_udp_handler
from ..handlers.null import build_null_handler
from ..handlers.otlp import OTLPConfig, build_otlp_handler
from ..handlers.syslog import SyslogConfig, build_syslog_handler
from .levels import ensure_level

__all__ = [
    "ExactLevelFilter",
    "MinLevelFilter",
    "LevelsAllowFilter",
    "build_formatter",
    "build_handler",
    "build_filter",
]


class LevelsAllowFilter(logging.Filter):
    """Allow only specific level numbers."""

    def __init__(self, levels: Iterable[int]) -> None:
        super().__init__()
        self.levels = {level for level in levels}

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno in self.levels


class MinLevelFilter(logging.Filter):
    """Allow records at or above a minimum level."""

    def __init__(self, minimum: int) -> None:
        super().__init__()
        self.minimum = minimum

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno >= self.minimum


class ExactLevelFilter(logging.Filter):
    """Allow only exact level matches."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno == self.level


FormatterBuilder = Callable[[FormatterSpec], logging.Formatter]
HandlerBuilder = Callable[[HandlerSpec, PathsConfig], logging.Handler]
FilterBuilder = Callable[[Dict[str, Any]], logging.Filter]


def _build_text(spec: FormatterSpec) -> logging.Formatter:
    return StructuredTextFormatter(**spec.options)


def _build_jsonl(spec: FormatterSpec) -> logging.Formatter:
    return JSONLinesFormatter(**spec.options)


def _build_logfmt(spec: FormatterSpec) -> logging.Formatter:
    return LogFmtFormatter(**spec.options)


def _build_csv(spec: FormatterSpec) -> logging.Formatter:
    return CSVFormatter(**spec.options)


FORMATTER_BUILDERS: Dict[str, FormatterBuilder] = {
    "text": _build_text,
    "jsonl": _build_jsonl,
    "logfmt": _build_logfmt,
    "csv": _build_csv,
}


def build_formatter(spec: FormatterSpec) -> logging.Formatter:
    builder = FORMATTER_BUILDERS.get(spec.kind)
    if builder is None:
        raise ValueError(f"Unknown formatter kind: {spec.kind}")
    return builder(spec)


def _build_file_handler(spec: HandlerSpec, paths: PathsConfig) -> logging.Handler:
    filename = spec.options.get("filename")
    if not filename:
        raise ValueError(f"Handler '{spec.name}' of type 'file' requires a filename")

    rotation_cfg = spec.options.get("rotation", {})
    size_rotation = None
    time_rotation = None
    if isinstance(rotation_cfg, dict):
        size_options = rotation_cfg.get("size")
        if isinstance(size_options, dict):
            size_rotation = SizeRotation(
                max_bytes=int(size_options.get("max_bytes", 10_000_000)),
                backup_count=int(size_options.get("backup_count", 5)),
            )
        time_options = rotation_cfg.get("time")
        if isinstance(time_options, dict):
            time_rotation = TimeRotation(
                when=str(time_options.get("when", "midnight")),
                interval=int(time_options.get("interval", 1)),
                backup_count=int(time_options.get("backup_count", 7)),
                utc=bool(time_options.get("utc", False)),
            )

    retention_cfg = spec.options.get("retention", {})
    if isinstance(retention_cfg, dict):
        max_files_raw = retention_cfg.get("max_files")
        max_days_raw = retention_cfg.get("max_days")
        retention = RetentionPolicy(
            max_files=int(max_files_raw) if max_files_raw is not None else None,
            max_days=int(max_days_raw) if max_days_raw is not None else None,
            compress=bool(retention_cfg.get("compress", False)),
        )
    else:
        retention = RetentionPolicy()

    encoding = spec.options.get("encoding")
    delay = bool(spec.options.get("delay", False))
    config = FileHandlerConfig(
        base_dir=paths.base_path,
        filename=str(filename),
        strategy=paths.strategy(),
        encoding=str(encoding) if encoding else None,
        size_rotation=size_rotation,
        time_rotation=time_rotation,
        retention=retention,
        delay=delay,
    )
    return build_file_handler(config)


def _build_console_handler(spec: HandlerSpec, paths: PathsConfig) -> logging.Handler:
    cfg = ConsoleHandlerConfig(stream=spec.options.get("stream", "stderr"))
    return build_console_handler(cfg)


def _build_syslog_handler(spec: HandlerSpec, paths: PathsConfig) -> logging.Handler:
    facility_raw = spec.options.get("facility", logging.handlers.SysLogHandler.LOG_USER)
    facility = int(facility_raw) if not isinstance(facility_raw, str) or facility_raw.isdigit() else logging.handlers.SysLogHandler.facility_names.get(facility_raw.lower(), logging.handlers.SysLogHandler.LOG_USER)

    socktype_raw = spec.options.get("socktype")
    if isinstance(socktype_raw, SocketKind):
        socktype = socktype_raw
    elif isinstance(socktype_raw, int):
        socktype = SocketKind(socktype_raw)
    else:
        socktype = None

    cfg = SyslogConfig(
        address=spec.options.get("address", ("localhost", 514)),
        facility=facility,
        socktype=socktype,
    )
    return build_syslog_handler(cfg)


def _build_gelf_handler(spec: HandlerSpec, paths: PathsConfig) -> logging.Handler:
    cfg = GELFUDPConfig(
        host=str(spec.options.get("host", "localhost")),
        port=int(spec.options.get("port", 12201)),
    )
    return build_gelf_udp_handler(cfg)


def _build_otlp_handler(spec: HandlerSpec, paths: PathsConfig) -> logging.Handler:
    cfg = OTLPConfig(
        endpoint=spec.options.get("endpoint"),
        insecure=bool(spec.options.get("insecure", False)),
        headers=spec.options.get("headers"),
        timeout=spec.options.get("timeout"),
        resource=spec.options.get("resource"),
        logger_name=str(spec.options.get("logger_name", "podlog")),
    )
    return build_otlp_handler(cfg)


def _build_null_handler(spec: HandlerSpec, paths: PathsConfig) -> logging.Handler:
    return build_null_handler()


HANDLER_BUILDERS: Dict[str, HandlerBuilder] = {
    "file": _build_file_handler,
    "console": _build_console_handler,
    "syslog": _build_syslog_handler,
    "gelf_udp": _build_gelf_handler,
    "otlp": _build_otlp_handler,
    "null": _build_null_handler,
}


def build_handler(spec: HandlerSpec, paths: PathsConfig) -> logging.Handler:
    builder = HANDLER_BUILDERS.get(spec.kind)
    if builder is None:
        raise ValueError(f"Unknown handler kind: {spec.kind}")
    return builder(spec, paths)


def _build_exact(params: Dict[str, Any]) -> logging.Filter:
    level = ensure_level(params.get("level", logging.INFO))
    return ExactLevelFilter(level)


def _build_min(params: Dict[str, Any]) -> logging.Filter:
    level = ensure_level(params.get("level", logging.INFO))
    return MinLevelFilter(level)


def _build_levels(params: Dict[str, Any]) -> logging.Filter:
    raw_levels = params.get("levels", [])
    levels = [ensure_level(value) for value in raw_levels]
    return LevelsAllowFilter(levels)


FILTER_BUILDERS: Dict[str, FilterBuilder] = {
    "exact": _build_exact,
    "min": _build_min,
    "levels": _build_levels,
}


def build_filter(spec: FilterSpec) -> logging.Filter:
    builder = FILTER_BUILDERS.get(spec.kind)
    if builder is None:
        raise ValueError(f"Unknown filter kind: {spec.kind}")
    return builder(spec.params)
