"""File handlers with rotation and retention support."""

from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

from ..utils.paths import DateFolderStrategy, build_log_path
from ..utils.time import utcnow

__all__ = [
    "SizeRotation",
    "TimeRotation",
    "RetentionPolicy",
    "FileHandlerConfig",
    "build_file_handler",
]


@dataclass(slots=True)
class SizeRotation:
    """Configure size-based rotation."""

    max_bytes: int
    backup_count: int = 5


@dataclass(slots=True)
class TimeRotation:
    """Configure time-based rotation."""

    when: str = "midnight"
    interval: int = 1
    backup_count: int = 7
    utc: bool = False


@dataclass(slots=True)
class RetentionPolicy:
    """Retention rules for rotated files."""

    max_files: int | None = None
    max_days: int | None = None
    compress: bool = False

    def apply(self, directory: Path, stem: str) -> None:
        if not directory.exists():
            return
        candidates = sorted(
            (path for path in directory.iterdir() if path.name.startswith(stem) and path.name != stem),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if self.max_files is not None and self.max_files >= 0:
            for path in candidates[self.max_files :]:
                path.unlink(missing_ok=True)

        if self.max_days is not None and self.max_days >= 0:
            cutoff = utcnow().timestamp() - (self.max_days * 86400)
            for path in candidates:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)


@dataclass(slots=True)
class FileHandlerConfig:
    """Aggregate configuration for file handlers."""

    base_dir: Path
    filename: str
    strategy: DateFolderStrategy
    encoding: str | None = "utf-8"
    size_rotation: SizeRotation | None = None
    time_rotation: TimeRotation | None = None
    retention: RetentionPolicy = field(default_factory=RetentionPolicy)
    delay: bool = False

    def __post_init__(self) -> None:
        if self.size_rotation and self.time_rotation:
            raise ValueError("Only one rotation strategy may be configured")
        if not self.size_rotation and not self.time_rotation:
            # Default to size rotation 10MB/5 files
            self.size_rotation = SizeRotation(max_bytes=10_000_000, backup_count=5)


class _DateAwareMixin:
    def __init__(self, *, config: FileHandlerConfig) -> None:
        self._config = config
        self._stem = config.filename
        self._current_dir = Path()
        self._update_path(moment=utcnow())

    def _resolve_path(self, moment: datetime) -> Path:
        return build_log_path(
            self._config.base_dir,
            self._config.filename,
            strategy=self._config.strategy,
            moment=moment,
        )

    def _update_path(self, moment: datetime) -> None:
        target = self._resolve_path(moment)
        directory = target.parent
        directory.mkdir(parents=True, exist_ok=True)
        if getattr(self, "baseFilename", "") != str(target):
            self.baseFilename = str(target)
            if getattr(self, "stream", None):
                self.stream.close()
                open_method = getattr(self, "_open", None)
                if callable(open_method):
                    self.stream = open_method()
        self._current_dir = directory

    def _apply_retention(self) -> None:
        self._config.retention.apply(self._current_dir, self._config.filename)


class DateAwareRotatingFileHandler(_DateAwareMixin, RotatingFileHandler):
    def __init__(self, *, config: FileHandlerConfig) -> None:
        initial_path = build_log_path(config.base_dir, config.filename, strategy=config.strategy, moment=utcnow())
        rot = config.size_rotation or SizeRotation(max_bytes=10_000_000, backup_count=5)
        RotatingFileHandler.__init__(
            self,
            filename=initial_path,
            maxBytes=rot.max_bytes,
            backupCount=rot.backup_count,
            encoding=config.encoding,
            delay=config.delay,
        )
        _DateAwareMixin.__init__(self, config=config)

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        self._update_path(datetime.fromtimestamp(record.created))
        super().emit(record)

    def doRollover(self) -> None:  # type: ignore[override]
        super().doRollover()
        if self._config.retention.compress:
            first_archive = Path(f"{self.baseFilename}.1")
            if first_archive.exists():
                self._compress(first_archive)
        self._apply_retention()

    def _compress(self, path: Path) -> None:
        target = path.with_suffix(path.suffix + ".gz")
        with path.open("rb") as src, gzip.open(target, "wb") as dst:
            dst.writelines(src)
        path.unlink(missing_ok=True)


class DateAwareTimedRotatingFileHandler(_DateAwareMixin, TimedRotatingFileHandler):
    def __init__(self, *, config: FileHandlerConfig) -> None:
        moment = utcnow()
        initial_path = build_log_path(config.base_dir, config.filename, strategy=config.strategy, moment=moment)
        rot = config.time_rotation or TimeRotation()
        TimedRotatingFileHandler.__init__(
            self,
            filename=initial_path,
            when=rot.when,
            interval=rot.interval,
            backupCount=rot.backup_count,
            encoding=config.encoding,
            delay=config.delay,
            utc=rot.utc,
        )
        _DateAwareMixin.__init__(self, config=config)

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        self._update_path(datetime.fromtimestamp(record.created))
        super().emit(record)

    def doRollover(self) -> None:  # type: ignore[override]
        super().doRollover()
        if self._config.retention.compress:
            first_archive = Path(f"{self.baseFilename}.1")
            if first_archive.exists():
                self._compress(first_archive)
        self._apply_retention()

    def _compress(self, path: Path) -> None:
        target = path.with_suffix(path.suffix + ".gz")
        with path.open("rb") as src, gzip.open(target, "wb") as dst:
            dst.writelines(src)
        path.unlink(missing_ok=True)


def build_file_handler(config: FileHandlerConfig) -> logging.Handler:
    """Create a file handler based on ``config``."""

    if config.time_rotation:
        return DateAwareTimedRotatingFileHandler(config=config)
    return DateAwareRotatingFileHandler(config=config)
