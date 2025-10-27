from __future__ import annotations

from pathlib import Path

import pytest

from podlog.config import loader


def test_configuration_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "podlog.toml").write_text("""[paths]\nbase_dir = \"user_logs\"\n""")
    monkeypatch.setattr(loader, "user_config_dir", lambda _: str(user_dir))

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "podlog.toml").write_text("""[paths]\nbase_dir = \"local_logs\"\n""")
    monkeypatch.chdir(project_dir)

    (project_dir / "pyproject.toml").write_text(
        """[tool.podlog.paths]\nbase_dir = \"pyproject_logs\"\n"""
    )

    monkeypatch.setenv("PODLOG__PATHS__BASE_DIR", "env_logs")

    config = loader.load_configuration({"paths": {"base_dir": "override_logs"}})
    assert config.paths.base_dir == Path("override_logs")

    config = loader.load_configuration({})
    assert config.paths.base_dir == Path("env_logs")

    monkeypatch.delenv("PODLOG__PATHS__BASE_DIR")
    config = loader.load_configuration({})
    assert config.paths.base_dir == Path("pyproject_logs")

    (project_dir / "pyproject.toml").unlink()
    config = loader.load_configuration({})
    assert config.paths.base_dir == Path("local_logs")

    (project_dir / "podlog.toml").unlink()
    config = loader.load_configuration({})
    assert config.paths.base_dir == Path("user_logs")


def test_env_config_trims_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PODLOG__LOGGING__ROOT__LEVEL", "  DEBUG  ")

    config = loader.load_configuration({})

    assert config.root_logger.level == "DEBUG"
