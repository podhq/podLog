"""Async logging helpers built on QueueHandler/QueueListener."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from typing import Iterable, List, cast

__all__ = ["QueueConfig", "QueueCoordinator"]


@dataclass(slots=True)
class QueueConfig:
    use_queue_listener: bool = True
    queue_maxsize: int = 1000
    flush_interval_ms: int = 500
    graceful_shutdown_timeout_s: float = 5.0


class QueueCoordinator:
    """Manage a queue-based logging pipeline."""

    def __init__(self, *, config: QueueConfig, handlers: Iterable[logging.Handler]) -> None:
        self.config = config
        self.handlers: List[logging.Handler] = list(handlers)
        self.queue: Queue[logging.LogRecord] = Queue(maxsize=config.queue_maxsize)
        self.queue_handler = _SafeQueueHandler(self.queue)
        self.listener = QueueListener(self.queue, *self.handlers, respect_handler_level=True)
        self._stop_event = threading.Event()
        self._flusher: threading.Thread | None = None
        if self.config.flush_interval_ms > 0:
            self._flusher = threading.Thread(target=self._flush_loop, daemon=True)

    def start(self) -> None:
        if not self.config.use_queue_listener:
            return
        self.listener.start()
        if self._flusher:
            self._flusher.start()

    def stop(self) -> None:
        if not self.config.use_queue_listener:
            return
        self._stop_event.set()
        if self._flusher and self._flusher.is_alive():
            self._flusher.join(timeout=self.config.graceful_shutdown_timeout_s)
        self.listener.stop()
        for handler in self.handlers:
            try:
                handler.flush()
            except Exception:
                continue

    def _flush_loop(self) -> None:
        interval = self.config.flush_interval_ms / 1000.0
        while not self._stop_event.wait(interval):
            for handler in self.handlers:
                try:
                    handler.flush()
                except Exception:
                    continue

    def __enter__(self) -> "QueueCoordinator":
        self.start()
        return self

    def __exit__(self, exc_type, exc: BaseException | None, tb) -> None:  # type: ignore[override]
        self.stop()

    def handler(self) -> logging.Handler:
        """Return the queue handler to attach to loggers."""

        return self.queue_handler


class _SafeQueueHandler(QueueHandler):
    """Queue handler that blocks instead of dropping records when full."""

    def enqueue(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        queue = cast(Queue[logging.LogRecord], self.queue)
        queue.put(record, block=True)
