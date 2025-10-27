from __future__ import annotations

import logging
from pathlib import Path

from podlog.handlers.file_rotating import (
    FileHandlerConfig,
    RetentionPolicy,
    SizeRotation,
    build_file_handler,
)
from podlog.utils.paths import DateFolderStrategy


def test_rotation_and_retention(tmp_path: Path) -> None:
    strategy = DateFolderStrategy(mode="flat", date_format="%Y%m%d")
    config = FileHandlerConfig(
        base_dir=tmp_path,
        filename="app.log",
        strategy=strategy,
        size_rotation=SizeRotation(max_bytes=128, backup_count=5),
        retention=RetentionPolicy(max_files=2, compress=True),
    )
    handler = build_file_handler(config)
    logger = logging.getLogger("podlog.rotation")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        for idx in range(40):
            logger.info("event-%s %s", idx, "x" * 50)
    finally:
        logger.removeHandler(handler)
        handler.flush()
        handler.close()

    folder = next(tmp_path.iterdir())
    archives = [p for p in folder.iterdir() if p.name.startswith("app.log.")]
    gz_archives = [p for p in archives if p.suffix.endswith("gz")]
    assert len(archives) <= 2
    assert gz_archives, "Expected compressed archives to be present"
