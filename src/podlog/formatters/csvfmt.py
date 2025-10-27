"""CSV formatter for podlog."""

from __future__ import annotations

import csv
import io
import logging
from typing import Iterable, Sequence

__all__ = ["CSVFormatter"]

_DEFAULT_FIELDS = ("ts", "level", "name", "context", "message")


class CSVFormatter(logging.Formatter):
    """Formatter that renders records as CSV rows."""

    def __init__(
        self,
        *,
        fields: Sequence[str] | None = None,
        extra_fields: Iterable[str] | None = None,
        include_header: bool = False,
        datefmt: str | None = "%Y-%m-%dT%H:%M:%S%z",
    ) -> None:
        super().__init__(datefmt=datefmt)
        self.fields = tuple(fields or _DEFAULT_FIELDS)
        self.extra_fields = list(extra_fields or [])
        self.include_header = include_header
        self._header_emitted = False

    def _value_for(self, record: logging.LogRecord, field: str) -> str:
        if field == "ts":
            return self.formatTime(record, self.datefmt)
        if field == "level":
            return record.levelname
        if field == "name":
            return record.name
        if field == "message":
            return record.getMessage()
        return str(getattr(record, field, ""))

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        if self.include_header and not self._header_emitted:
            writer.writerow([*self.fields, *self.extra_fields])
            self._header_emitted = True

        row = [self._value_for(record, field) for field in self.fields]
        data = record.__dict__
        row.extend(str(data.get(field, "")) for field in self.extra_fields)
        writer.writerow(row)

        return buffer.getvalue().strip("\n")
