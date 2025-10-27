from __future__ import annotations

from pathlib import Path

from podlog import api
from podlog.core.manager import GLOBAL_MANAGER


def test_queue_shutdown_flushes(tmp_path: Path) -> None:
    overrides = {
        "paths": {"base_dir": str(tmp_path), "date_folder_mode": "flat"},
        "formatters": {"text": {"base": {}}},
        "handlers": {
            "enabled": ["queue_file"],
            "queue_file": {
                "type": "file",
                "level": "INFO",
                "formatter": "text.base",
                "filename": "queue.log",
            },
        },
        "logging": {
            "root": {"level": "INFO", "handlers": ["queue_file"]},
        },
        "async": {
            "use_queue_listener": True,
            "queue_maxsize": 5,
            "flush_interval_ms": 10,
            "graceful_shutdown_timeout_s": 1.0,
        },
    }

    api.configure(overrides)
    logger = api.get_logger("tests.queue")
    for idx in range(20):
        logger.info("queued %s", idx)

    GLOBAL_MANAGER.shutdown()

    folder = next(tmp_path.iterdir())
    contents = (folder / "queue.log").read_text(encoding="utf-8").strip().splitlines()
    assert len(contents) == 20
