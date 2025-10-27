"""Configuration schema definition for podlog."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping

from ..handlers.queue_async import QueueConfig
from ..utils.paths import DateFolderMode, DateFolderStrategy

DEFAULT_CONFIG: Dict[str, Any] = {
    "paths": {
        "base_dir": "logs",
        "date_folder_mode": "nested",
        "date_format": "%Y-%m-%d",
    },
    "formatters": {
        "text": {
            "default": {"show_extras": False},
        },
        "jsonl": {
            "default": {},
        },
        "logfmt": {
            "default": {},
        },
        "csv": {
            "default": {},
        },
    },
    "filters": {},
    "handlers": {
        "enabled": ["console"],
        "console": {
            "type": "console",
            "level": "INFO",
            "formatter": "text.default",
            "stream": "stderr",
        },
    },
    "logging": {
        "root": {
            "level": "INFO",
            "handlers": ["console"],
        },
        "loggers": {},
        "disable_existing_loggers": False,
        "force_config": False,
        "incremental": False,
        "capture_warnings": True,
    },
    "levels": {
        "root": "INFO",
        "enable_trace": False,
        "overrides": {},
    },
    "async": {
        "use_queue_listener": False,
        "queue_maxsize": 1000,
        "flush_interval_ms": 500,
        "graceful_shutdown_timeout_s": 5.0,
    },
    "context": {
        "enabled": True,
        "allowed_keys": [],
    },
}


def default_config() -> Dict[str, Any]:
    """Return a deep copy of the default configuration mapping."""

    return deepcopy(DEFAULT_CONFIG)


@dataclass(slots=True)
class PathsConfig:
    base_dir: Path
    date_folder_mode: DateFolderMode
    date_format: str

    @property
    def base_path(self) -> Path:
        return self.base_dir

    def strategy(self) -> DateFolderStrategy:
        return DateFolderStrategy(mode=self.date_folder_mode, date_format=self.date_format)


@dataclass(slots=True)
class FormatterSpec:
    name: str
    kind: str
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FilterSpec:
    name: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HandlerSpec:
    name: str
    kind: str
    level: str | int
    formatter: str
    filters: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LoggerSpec:
    name: str
    level: str | int
    handlers: List[str] = field(default_factory=list)
    propagate: bool = False


@dataclass(slots=True)
class LevelsConfig:
    root_level: str | int
    enable_trace: bool
    overrides: Dict[str, str | int] = field(default_factory=dict)


@dataclass(slots=True)
class ContextConfig:
    enabled: bool = True
    allowed_keys: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PodlogConfig:
    paths: PathsConfig
    formatters: Dict[str, FormatterSpec]
    filters: Dict[str, FilterSpec]
    handlers: Dict[str, HandlerSpec]
    handlers_enabled: List[str]
    loggers: Dict[str, LoggerSpec]
    root_logger: LoggerSpec
    levels: LevelsConfig
    async_config: QueueConfig
    context: ContextConfig
    capture_warnings: bool
    disable_existing_loggers: bool
    force_config: bool
    incremental: bool
    raw: Dict[str, Any] = field(repr=False)

    def formatter(self, name: str) -> FormatterSpec:
        return self.formatters[name]

    def handler(self, name: str) -> HandlerSpec:
        return self.handlers[name]

    def logger(self, name: str) -> LoggerSpec:
        return self.loggers[name]


def _to_paths_config(data: Mapping[str, Any]) -> PathsConfig:
    base_dir = Path(data.get("base_dir", "logs"))
    mode = data.get("date_folder_mode", "nested")
    date_format = data.get("date_format", "%Y-%m-%d")
    return PathsConfig(base_dir=base_dir, date_folder_mode=mode, date_format=date_format)


def _to_formatters(data: Mapping[str, Any]) -> Dict[str, FormatterSpec]:
    specs: Dict[str, FormatterSpec] = {}
    for kind, entries in data.items():
        if not isinstance(entries, Mapping):
            continue
        for name, options in entries.items():
            key = f"{kind}.{name}"
            opts = dict(options or {}) if isinstance(options, Mapping) else {}
            specs[key] = FormatterSpec(name=key, kind=kind, options=opts)
    return specs


def _to_filters(data: Mapping[str, Any]) -> Dict[str, FilterSpec]:
    filters: Dict[str, FilterSpec] = {}
    for name, payload in data.items():
        if not isinstance(payload, Mapping):
            continue
        kind = str(payload.get("type", "min")).lower()
        params = {k: v for k, v in payload.items() if k != "type"}
        filters[name] = FilterSpec(name=name, kind=kind, params=params)
    return filters


def _to_handlers(data: Mapping[str, Any]) -> tuple[Dict[str, HandlerSpec], List[str]]:
    handlers: Dict[str, HandlerSpec] = {}
    enabled_raw = data.get("enabled")
    enabled: List[str]
    if isinstance(enabled_raw, list):
        enabled = [str(item) for item in enabled_raw]
    else:
        enabled = []

    for name, payload in data.items():
        if name == "enabled" or not isinstance(payload, Mapping):
            continue
        kind = str(payload.get("type", "console"))
        level = payload.get("level", "INFO")
        formatter = payload.get("formatter", "text.default")
        filters = [str(f) for f in payload.get("filters", [])] if "filters" in payload else []
        options = {
            key: value
            for key, value in payload.items()
            if key not in {"type", "level", "formatter", "filters"}
        }
        handlers[name] = HandlerSpec(
            name=name,
            kind=kind,
            level=level,
            formatter=str(formatter),
            filters=filters,
            options=dict(options),
        )

    if not enabled:
        enabled = list(handlers.keys())
    return handlers, enabled


def _to_loggers(data: Mapping[str, Any]) -> tuple[LoggerSpec, Dict[str, LoggerSpec], bool, bool, bool, bool]:
    root_data = data.get("root", {})
    if not isinstance(root_data, Mapping):
        root_data = {}
    loggers_data = data.get("loggers", {})
    if not isinstance(loggers_data, Mapping):
        loggers_data = {}

    disable_existing = bool(data.get("disable_existing_loggers", False))
    force_config = bool(data.get("force_config", False))
    incremental = bool(data.get("incremental", False))
    capture_warnings = bool(data.get("capture_warnings", True))

    def _build_logger(name: str, payload: Mapping[str, Any]) -> LoggerSpec:
        level = payload.get("level", "INFO")
        handlers = [str(h) for h in payload.get("handlers", [])]
        propagate = bool(payload.get("propagate", False))
        return LoggerSpec(name=name, level=level, handlers=handlers, propagate=propagate)

    root_handlers = root_data.get("handlers")
    root_handlers_list = [str(h) for h in root_handlers] if isinstance(root_handlers, list) else []
    root_level = root_data.get("level", "INFO")
    root_spec = LoggerSpec(name="root", level=root_level, handlers=root_handlers_list, propagate=False)

    specs: Dict[str, LoggerSpec] = {}
    for name, payload in loggers_data.items():
        if isinstance(payload, Mapping):
            specs[name] = _build_logger(name, payload)

    return root_spec, specs, disable_existing, force_config, incremental, capture_warnings


def _to_levels(data: Mapping[str, Any]) -> LevelsConfig:
    root_level = data.get("root", "INFO")
    enable_trace = bool(data.get("enable_trace", False))
    overrides_raw = data.get("overrides", {})
    overrides: Dict[str, str | int] = {}
    if isinstance(overrides_raw, Mapping):
        for name, value in overrides_raw.items():
            overrides[name] = value
    return LevelsConfig(root_level=root_level, enable_trace=enable_trace, overrides=overrides)


def _to_async(data: Mapping[str, Any]) -> QueueConfig:
    return QueueConfig(
        use_queue_listener=bool(data.get("use_queue_listener", False)),
        queue_maxsize=int(data.get("queue_maxsize", 1000)),
        flush_interval_ms=int(data.get("flush_interval_ms", 500)),
        graceful_shutdown_timeout_s=float(data.get("graceful_shutdown_timeout_s", 5.0)),
    )


def _to_context(data: Mapping[str, Any]) -> ContextConfig:
    enabled = bool(data.get("enabled", True))
    allowed_raw = data.get("allowed_keys", [])
    if isinstance(allowed_raw, Mapping):
        allowed = [str(item) for item in allowed_raw.keys()]
    elif isinstance(allowed_raw, Iterable) and not isinstance(allowed_raw, (str, bytes)):
        allowed = [str(item) for item in allowed_raw]
    else:
        allowed = []
    return ContextConfig(enabled=enabled, allowed_keys=allowed)


def build_config(data: Mapping[str, Any]) -> PodlogConfig:
    paths = _to_paths_config(data.get("paths", {}))
    formatters = _to_formatters(data.get("formatters", {}))
    filters = _to_filters(data.get("filters", {}))
    handlers, enabled = _to_handlers(data.get("handlers", {}))
    root_logger, loggers, disable_existing, force_config, incremental, capture_warnings = _to_loggers(data.get("logging", {}))
    levels = _to_levels(data.get("levels", {}))
    async_config = _to_async(data.get("async", {}))
    context = _to_context(data.get("context", {}))

    if not root_logger.handlers:
        root_logger.handlers = enabled.copy()

    raw_copy: Dict[str, Any] = deepcopy({k: v for k, v in data.items()})

    return PodlogConfig(
        paths=paths,
        formatters=formatters,
        filters=filters,
        handlers=handlers,
        handlers_enabled=enabled,
        loggers=loggers,
        root_logger=root_logger,
        levels=levels,
        async_config=async_config,
        context=context,
        capture_warnings=capture_warnings,
        disable_existing_loggers=disable_existing,
        force_config=force_config,
        incremental=incremental,
        raw=raw_copy,
    )
