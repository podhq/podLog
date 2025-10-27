from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from podlog import api
from podlog.core.manager import GLOBAL_MANAGER


def _dated_folder(base_dir: Path) -> Path:
    today = datetime.now()
    return base_dir / today.strftime("%Y-%m-%d")


def test_context_and_formatters(tmp_path: Path) -> None:
    overrides = {
        "paths": {"base_dir": str(tmp_path), "date_folder_mode": "flat"},
        "formatters": {
            "text": {"human": {"show_extras": True}},
            "jsonl": {"audit": {}},
        },
        "handlers": {
            "enabled": ["text_file", "json_file"],
            "text_file": {
                "type": "file",
                "level": "INFO",
                "formatter": "text.human",
                "filename": "text.log",
            },
            "json_file": {
                "type": "file",
                "level": "INFO",
                "formatter": "jsonl.audit",
                "filename": "events.jsonl",
            },
        },
        "logging": {
            "root": {"level": "INFO", "handlers": ["text_file", "json_file"]},
        },
    }

    api.configure(overrides)
    logger = api.get_context_logger("tests.context", request_id="abc123")
    logger.add_extra(order=42)
    logger.info("hello world")
    GLOBAL_MANAGER.shutdown()

    folder = _dated_folder(tmp_path)
    text_path = folder / "text.log"
    json_path = folder / "events.jsonl"

    text_line = text_path.read_text(encoding="utf-8").strip()
    assert "request_id=abc123" in text_line
    assert "order=42" in text_line

    json_record = json.loads(json_path.read_text(encoding="utf-8").strip())
    assert json_record["context"] == "request_id=abc123"
    assert json_record["extra"]["order"] == 42
