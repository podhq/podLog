"""OTLP logging handler helpers."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Mapping, cast

__all__ = ["OTLPConfig", "build_otlp_handler"]

def _load_otlp_dependencies() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    logs_module = importlib.import_module("opentelemetry.sdk._logs")
    export_module = importlib.import_module("opentelemetry.sdk._logs.export")
    resources_module = importlib.import_module("opentelemetry.sdk.resources")
    logger_provider = getattr(logs_module, "LoggerProvider")
    logging_handler = getattr(logs_module, "LoggingHandler")
    batch_processor = getattr(export_module, "BatchLogRecordProcessor")
    exporter = getattr(export_module, "OTLPLogExporter")
    resource = getattr(resources_module, "Resource")
    return logger_provider, logging_handler, batch_processor, exporter, resource


@dataclass(slots=True)
class OTLPConfig:
    endpoint: str | None = None
    insecure: bool = False
    headers: Mapping[str, str] | None = None
    timeout: float | None = None
    resource: Mapping[str, str] | None = None
    logger_name: str = "podlog"


def build_otlp_handler(config: OTLPConfig | None = None) -> logging.Handler:
    """Build a handler that forwards to an OTLP collector."""

    cfg = config or OTLPConfig()
    try:
        (
            logger_provider_cls,
            logging_handler_cls,
            batch_processor_cls,
            exporter_cls,
            resource_cls,
        ) = _load_otlp_dependencies()
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency missing
        raise RuntimeError("OTLP support requires opentelemetry-sdk to be installed") from exc

    resource = cast(Any, resource_cls).create(dict(cfg.resource or {}))
    provider = cast(Any, logger_provider_cls)(resource=resource)

    exporter_kwargs: Dict[str, object] = {"insecure": cfg.insecure}
    if cfg.endpoint:
        exporter_kwargs["endpoint"] = cfg.endpoint
    if cfg.headers:
        exporter_kwargs["headers"] = dict(cfg.headers)
    if cfg.timeout is not None:
        exporter_kwargs["timeout"] = cfg.timeout

    exporter = cast(Any, exporter_cls)(**exporter_kwargs)
    batch_processor = cast(Any, batch_processor_cls)(exporter)
    provider.add_log_record_processor(batch_processor)
    handler = cast(Any, logging_handler_cls)(level=logging.NOTSET, logger_provider=provider)
    handler.logger.name = cfg.logger_name
    return handler
