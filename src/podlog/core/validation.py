"""Configuration validation helpers."""

from __future__ import annotations

from ..config.schema import PodlogConfig


class ConfigurationError(ValueError):
    """Raised when configuration validation fails."""


def validate_configuration(config: PodlogConfig) -> None:
    """Ensure configuration references are consistent."""

    missing_handlers = [name for name in config.handlers_enabled if name not in config.handlers]
    if missing_handlers:
        raise ConfigurationError(
            f"Handlers referenced in 'enabled' but undefined: {', '.join(missing_handlers)}"
        )

    if not config.handlers_enabled:
        raise ConfigurationError("At least one handler must be enabled")

    enabled_set = set(config.handlers_enabled)

    for handler in config.handlers.values():
        if handler.formatter not in config.formatters:
            raise ConfigurationError(f"Handler '{handler.name}' references unknown formatter '{handler.formatter}'")
        for filter_name in handler.filters:
            if filter_name not in config.filters:
                raise ConfigurationError(f"Handler '{handler.name}' references unknown filter '{filter_name}'")

    for handler_name in config.root_logger.handlers:
        if handler_name not in config.handlers:
            raise ConfigurationError(f"Root logger references unknown handler '{handler_name}'")
        if handler_name not in enabled_set:
            raise ConfigurationError(
                f"Root logger references handler '{handler_name}' which is not enabled"
            )

    for logger in config.loggers.values():
        for handler_name in logger.handlers:
            if handler_name not in config.handlers:
                raise ConfigurationError(f"Logger '{logger.name}' references unknown handler '{handler_name}'")
            if handler_name not in enabled_set:
                raise ConfigurationError(
                    f"Logger '{logger.name}' references handler '{handler_name}' which is not enabled"
                )
