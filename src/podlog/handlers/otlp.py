"""OTLP logging handler helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Mapping

__all__ = ["OTLPConfig", "build_otlp_handler"]

try:  # pragma: no cover - optional dependency
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, OTLPLogExporter
    from opentelemetry.sdk.resources import Resource
except Exception:  # pragma: no cover - fallback when OTLP not installed
    LoggerProvider = None  # type: ignore[assignment]
    LoggingHandler = None  # type: ignore[assignment]
    BatchLogRecordProcessor = None  # type: ignore[assignment]
    OTLPLogExporter = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]


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

    if LoggingHandler is None or LoggerProvider is None:
        raise RuntimeError("OTLP support requires opentelemetry-sdk to be installed")

    cfg = config or OTLPConfig()
    resource = Resource.create(dict(cfg.resource or {}))
    provider = LoggerProvider(resource=resource)

    exporter_kwargs: Dict[str, object] = {"insecure": cfg.insecure}
    if cfg.endpoint:
        exporter_kwargs["endpoint"] = cfg.endpoint
    if cfg.headers:
        exporter_kwargs["headers"] = dict(cfg.headers)
    if cfg.timeout is not None:
        exporter_kwargs["timeout"] = cfg.timeout

    exporter = OTLPLogExporter(**exporter_kwargs)
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
    handler.logger.name = cfg.logger_name
    return handler
