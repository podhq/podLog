"""Context-aware logging adapter and helpers."""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Tuple

from .levels import TRACE_LEVEL_NUM


@dataclass(slots=True)
class ContextState:
    """Container for persistent context and buffered extras."""

    context: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    def context_string(self) -> str:
        items = sorted(self.context.items(), key=lambda kv: kv[0])
        return " ".join(f"{key}={value}" for key, value in items) if items else "-"

    def extras_text(self, data: Mapping[str, Any]) -> str:
        if not data:
            return "-"
        parts: list[str] = []
        for key, value in data.items():
            if key in {"context", "extra_kvs"}:
                continue
            try:
                rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            except Exception:
                rendered = repr(value)
            parts.append(f"{key}={rendered}")
        return " ".join(parts)


class ContextFilter(logging.Filter):
    """Ensure context attributes exist on log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.__dict__.setdefault("context", "-")
        record.__dict__.setdefault("extra_kvs", "-")
        return True


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that keeps persistent context and extras.

    The adapter exposes helpers to manage state and inject the ``extra`` mapping
    into ``LogRecord`` objects so formatters can access ``%(context)s`` and
    ``%(extra_kvs)s`` placeholders.
    """

    def __init__(self, logger: logging.Logger, *, base_context: Mapping[str, Any] | None = None) -> None:
        super().__init__(logger, {})
        self._state = ContextState(context=dict(base_context or {}))

    # -- Context management -------------------------------------------------
    def set_context(self, ctx: Mapping[str, Any] | str) -> None:
        if isinstance(ctx, str):
            self._state.context = self._parse_ctx_string(ctx)
        else:
            self._state.context = dict(ctx)

    def add_context(self, **kwargs: Any) -> None:
        self._state.context.update(kwargs)

    def clear_extra(self) -> None:
        self._state.extras.clear()

    def add_extra(self, *args: Any, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            self._state.extras[key] = value

        if not args:
            return

        frame = inspect.currentframe()
        try:
            caller = frame.f_back if frame else None
            names_by_id: Dict[int, str] = {}
            if caller is not None:
                for name, value in caller.f_locals.items():
                    names_by_id[id(value)] = name

            used = set(self._state.extras.keys())
            counter = 1
            for value in args:
                inferred = names_by_id.get(id(value))
                if not inferred or inferred in used:
                    while True:
                        candidate = f"var{counter}"
                        counter += 1
                        if candidate not in used:
                            inferred = candidate
                            break
                self._state.extras[inferred] = value
                used.add(inferred)
        finally:
            del frame

    # -- LoggingAdapter API -------------------------------------------------
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> Tuple[str, MutableMapping[str, Any]]:
        call_extra = kwargs.get("extra")
        merged: Dict[str, Any] = dict(self._state.extras)
        if isinstance(call_extra, Mapping):
            merged.update(call_extra)

        merged["context"] = self._state.context_string()
        merged["extra_kvs"] = self._state.extras_text(merged)
        kwargs["extra"] = merged
        return msg, kwargs

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.logger.isEnabledFor(TRACE_LEVEL_NUM):
            self.log(TRACE_LEVEL_NUM, msg, *args, **kwargs)

    # -- Helpers ------------------------------------------------------------
    @staticmethod
    def _parse_ctx_string(value: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        parts = [part for part in value.strip().split() if part]
        for part in parts:
            if "=" not in part:
                continue
            key, raw = part.split("=", 1)
            result[key] = raw
        return result or {"_ctx": value}


def ensure_context_filter(logger: logging.Logger) -> None:
    """Attach the :class:`ContextFilter` to ``logger`` if missing."""

    for existing in logger.filters:
        if isinstance(existing, ContextFilter):
            return
    logger.addFilter(ContextFilter())


def inject_context(logger: logging.Logger, *, base_context: Mapping[str, Any] | None = None) -> ContextAdapter:
    """Return a :class:`ContextAdapter` attached to ``logger`` with filter."""

    ensure_context_filter(logger)
    return ContextAdapter(logger, base_context=base_context)
