"""Path synthesis helpers for log files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

DateFolderMode = Literal["flat", "nested"]

__all__ = [
    "DateFolderMode",
    "DateFolderStrategy",
    "ensure_directory",
    "dated_directory",
    "build_log_path",
]


@dataclass(slots=True)
class DateFolderStrategy:
    """Options controlling how date folders are laid out."""

    mode: DateFolderMode = "nested"
    date_format: str = "%Y-%m-%d"


def ensure_directory(path: str | Path) -> Path:
    """Ensure the directory for ``path`` exists and return it as ``Path``."""

    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def dated_directory(base_dir: str | Path, *, strategy: DateFolderStrategy, moment: datetime) -> Path:
    """Return the directory for ``moment`` according to ``strategy``."""

    base = ensure_directory(base_dir)
    if strategy.mode == "flat":
        folder = strategy.date_format
        formatted = moment.strftime(folder)
        return ensure_directory(base / formatted)

    return ensure_directory(base / f"{moment.year:04d}" / f"{moment.month:02d}" / f"{moment.day:02d}")


def build_log_path(
    base_dir: str | Path,
    filename: str,
    *,
    strategy: DateFolderStrategy,
    moment: datetime,
) -> Path:
    """Build the full path for a log file given the current ``moment``."""

    directory = dated_directory(base_dir, strategy=strategy, moment=moment)
    return directory / filename
