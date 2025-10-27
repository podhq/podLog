from __future__ import annotations

from datetime import datetime
from pathlib import Path

from podlog.utils.paths import DateFolderStrategy, build_log_path


def test_build_log_path_nested(tmp_path: Path) -> None:
    moment = datetime(2023, 1, 2, 3, 4, 5)
    strategy = DateFolderStrategy(mode="nested")
    path = build_log_path(tmp_path, "app.log", strategy=strategy, moment=moment)
    assert path.parent == tmp_path / "2023" / "01" / "02"
    assert path.name == "app.log"


def test_build_log_path_flat(tmp_path: Path) -> None:
    moment = datetime(2023, 12, 31)
    strategy = DateFolderStrategy(mode="flat", date_format="%Y%m%d")
    path = build_log_path(tmp_path, "audit.log", strategy=strategy, moment=moment)
    assert path.parent == tmp_path / "20231231"
    assert path.name == "audit.log"
