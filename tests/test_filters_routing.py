from __future__ import annotations

from pathlib import Path

from podlog import api
from podlog.core.manager import GLOBAL_MANAGER


def test_filters_route_records(tmp_path: Path) -> None:
    overrides = {
        "paths": {"base_dir": str(tmp_path), "date_folder_mode": "flat"},
        "formatters": {"text": {"base": {}}},
        "filters": {
            "warn_only": {"type": "min", "level": "WARNING"},
            "info_only": {"type": "exact", "level": "INFO"},
        },
        "handlers": {
            "enabled": ["info_file", "warn_file"],
            "info_file": {
                "type": "file",
                "level": "INFO",
                "formatter": "text.base",
                "filename": "info.log",
                "filters": ["info_only"],
            },
            "warn_file": {
                "type": "file",
                "level": "WARNING",
                "formatter": "text.base",
                "filename": "warn.log",
                "filters": ["warn_only"],
            },
        },
        "logging": {
            "root": {"level": "INFO", "handlers": ["info_file", "warn_file"]},
        },
    }

    api.configure(overrides)
    logger = api.get_logger("tests.filters")
    logger.info("info message")
    logger.warning("warning message")
    GLOBAL_MANAGER.shutdown()

    folder = next(tmp_path.iterdir())
    info_lines = (folder / "info.log").read_text(encoding="utf-8").strip().splitlines()
    warn_lines = (folder / "warn.log").read_text(encoding="utf-8").strip().splitlines()

    assert any("info message" in line for line in info_lines)
    assert not any("warning message" in line for line in info_lines)
    assert any("warning message" in line for line in warn_lines)
    assert not any("info message" in line for line in warn_lines)
