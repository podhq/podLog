"""Configuration loading pipeline."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Mapping, cast

from platformdirs import user_config_dir

from .schema import PodlogConfig, build_config, default_config

try:  # pragma: no cover
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

try:  # pragma: no cover
    yaml_module = importlib.import_module("yaml")
except ModuleNotFoundError:  # pragma: no cover
    yaml_module = None

yaml: ModuleType | None = yaml_module


_ENV_PREFIX = "PODLOG__"


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        loader = getattr(yaml, "safe_load", None)
        if not callable(loader):
            return {}
        yaml_loader = cast(Callable[[Any], Any], loader)
        data = yaml_loader(fh)
    if isinstance(data, Mapping):
        return {str(key): value for key, value in data.items()}
    return {}


def _merge(base: Dict[str, Any], incoming: Mapping[str, Any]) -> Dict[str, Any]:
    for key, value in incoming.items():
        existing = base.get(key)
        if isinstance(value, Mapping) and isinstance(existing, dict):
            _merge(existing, value)
        elif isinstance(value, Mapping) and isinstance(existing, Mapping):
            nested = dict(existing)
            base[key] = _merge(nested, value)
        elif isinstance(value, Mapping):
            base[key] = _merge({}, value)
        else:
            base[key] = value
    return base


def _load_user_config() -> Dict[str, Any]:
    cfg_dir = Path(user_config_dir("podlog"))
    if not cfg_dir.exists():
        return {}
    data: Dict[str, Any] = {}
    for filename in ("podlog.toml", "podlog.yaml", "podlog.yml"):
        payload = (
            _load_toml(cfg_dir / filename)
            if filename.endswith(".toml")
            else _load_yaml(cfg_dir / filename)
        )
        if payload:
            data = _merge(data, payload)
    return data


def _load_local_config() -> Dict[str, Any]:
    cwd = Path.cwd()
    data: Dict[str, Any] = {}
    for filename in ("podlog.toml", "podlog.yaml", "podlog.yml"):
        path = cwd / filename
        payload = _load_toml(path) if filename.endswith(".toml") else _load_yaml(path)
        if payload:
            data = _merge(data, payload)
    return data


def _load_pyproject() -> Dict[str, Any]:
    path = Path("pyproject.toml")
    if not path.exists():
        return {}
    data = _load_toml(path)
    tool = data.get("tool", {})
    if not isinstance(tool, Mapping):
        return {}
    podlog = tool.get("podlog", {})
    if isinstance(podlog, Mapping):
        return {str(key): value for key, value in podlog.items()}
    return {}


def _coerce_value(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(stripped)
    except ValueError:
        try:
            return float(stripped)
        except ValueError:
            pass
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    return stripped


def _env_config() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for env_key, raw_value in os.environ.items():
        if not env_key.startswith(_ENV_PREFIX):
            continue
        path = env_key[len(_ENV_PREFIX) :].split("__")
        target: Dict[str, Any] = data
        for segment in path[:-1]:
            seg = segment.lower()
            child = target.setdefault(seg, {})
            target = cast(Dict[str, Any], child)
        target[path[-1].lower()] = _coerce_value(raw_value)
    return data


def _merge_overrides(*mappings: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = default_config()
    for mapping in mappings:
        if mapping:
            _merge(result, mapping)
    return result


def load_configuration(overrides: Dict[str, Any] | None = None) -> PodlogConfig:
    """Load configuration from supported sources in precedence order."""

    overrides = overrides or {}
    merged = _merge_overrides(
        _load_user_config(),
        _load_local_config(),
        _load_pyproject(),
        _env_config(),
        overrides,
    )
    return build_config(merged)
