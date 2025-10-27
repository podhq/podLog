"""Logging manager responsible for runtime configuration and lifecycle."""

from __future__ import annotations

import logging
from typing import Dict, Set

from ..config.schema import PodlogConfig
from ..handlers.queue_async import QueueCoordinator
from .context import ContextAdapter, inject_context
from .levels import ensure_level, register_trace_level
from .registry import build_filter, build_formatter, build_handler
from .validation import validate_configuration


class LogManager:
    """Central coordinator for podlog configuration."""

    def __init__(self) -> None:
        self._config: PodlogConfig | None = None
        self._handlers: Dict[str, logging.Handler] = {}
        self._real_handlers: Dict[str, logging.Handler] = {}
        self._coordinators: Dict[str, QueueCoordinator] = {}
        self._configured_loggers: Set[str] = set()
        self._formatters_cache: Dict[str, logging.Formatter] = {}
        self._filters_cache: Dict[str, logging.Filter] = {}

    # ------------------------------------------------------------------
    def configure(self, config: PodlogConfig) -> None:
        """Apply the supplied configuration."""

        validate_configuration(config)
        self._teardown()

        self._config = config
        register_trace_level(config.levels.enable_trace)
        logging.captureWarnings(config.capture_warnings)

        self._formatters_cache = {
            name: build_formatter(spec) for name, spec in config.formatters.items()
        }
        self._filters_cache = {
            name: build_filter(spec) for name, spec in config.filters.items()
        }

        self._real_handlers = {}
        for name in config.handlers_enabled:
            spec = config.handlers[name]
            handler = build_handler(spec, config.paths)
            handler.setLevel(ensure_level(spec.level))
            formatter = self._formatters_cache[spec.formatter]
            handler.setFormatter(formatter)
            for filter_name in spec.filters:
                handler.addFilter(self._filters_cache[filter_name])
            self._real_handlers[name] = handler

        self._handlers = {}
        self._coordinators = {}
        async_cfg = config.async_config if config.async_config.use_queue_listener else None
        if async_cfg:
            for name, handler in self._real_handlers.items():
                coordinator = QueueCoordinator(config=async_cfg, handlers=[handler])
                coordinator.start()
                queue_handler = coordinator.handler()
                queue_handler.setLevel(handler.level)
                for filt in handler.filters:
                    queue_handler.addFilter(filt)
                self._coordinators[name] = coordinator
                self._handlers[name] = queue_handler
        else:
            self._handlers = dict(self._real_handlers)

        self._configured_loggers = set()
        self._configure_root_logger()
        self._configure_named_loggers()
        self._apply_level_overrides()
        if config.disable_existing_loggers:
            self._disable_unconfigured_loggers()

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Shutdown queue listeners and close handlers."""

        self._teardown()
        self._config = None

    # ------------------------------------------------------------------
    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)

    def get_context_logger(self, name: str, **context_kv: object) -> ContextAdapter:
        logger = self.get_logger(name)
        if self._config and not self._config.context.enabled:
            base = {}
        else:
            base = dict(context_kv)
            if self._config and self._config.context.allowed_keys:
                allowed = set(self._config.context.allowed_keys)
                base = {k: v for k, v in base.items() if k in allowed}
        adapter = inject_context(logger, base_context=base)
        return adapter

    # ------------------------------------------------------------------
    def _teardown(self) -> None:
        handlers_to_remove = set(self._handlers.values()) | set(self._real_handlers.values())
        if handlers_to_remove:
            root_logger = logging.getLogger()
            for handler in list(root_logger.handlers):
                if handler in handlers_to_remove:
                    root_logger.removeHandler(handler)
            for logger_name in self._configured_loggers:
                if logger_name == "root":
                    continue
                logger = logging.getLogger(logger_name)
                for handler in list(logger.handlers):
                    if handler in handlers_to_remove:
                        logger.removeHandler(handler)

        for coordinator in self._coordinators.values():
            coordinator.stop()
        self._coordinators.clear()

        for handler in self._handlers.values():
            try:
                handler.flush()
            except Exception:
                pass
            handler.close()

        for handler in self._real_handlers.values():
            try:
                handler.flush()
            except Exception:
                pass
            handler.close()

        self._handlers.clear()
        self._real_handlers.clear()
        self._configured_loggers.clear()

    def _configure_root_logger(self) -> None:
        assert self._config is not None
        root_logger = logging.getLogger()
        root_logger.handlers = []
        root_level = ensure_level(self._config.levels.root_level or self._config.root_logger.level)
        root_logger.setLevel(root_level)
        for handler_name in self._config.root_logger.handlers:
            handler = self._handlers.get(handler_name)
            if handler is not None:
                root_logger.addHandler(handler)
        root_logger.propagate = False
        self._configured_loggers.add("root")

    def _configure_named_loggers(self) -> None:
        assert self._config is not None
        for name, spec in self._config.loggers.items():
            logger = logging.getLogger(name)
            logger.handlers = []
            level_value = spec.level
            if name in self._config.levels.overrides:
                level_value = self._config.levels.overrides[name]
            logger.setLevel(ensure_level(level_value))
            for handler_name in spec.handlers:
                handler = self._handlers.get(handler_name)
                if handler is not None:
                    logger.addHandler(handler)
            logger.propagate = spec.propagate
            self._configured_loggers.add(name)

    def _apply_level_overrides(self) -> None:
        assert self._config is not None
        for name, level in self._config.levels.overrides.items():
            if name in self._config.loggers:
                continue
            logger = logging.getLogger(name)
            logger.setLevel(ensure_level(level))

    def _disable_unconfigured_loggers(self) -> None:
        configured = set(self._configured_loggers)
        manager = logging.getLogger().manager
        for name in list(manager.loggerDict.keys()):
            if not name or name in configured:
                continue
            logger = logging.getLogger(name)
            logger.disabled = True


GLOBAL_MANAGER = LogManager()
