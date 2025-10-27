"""Configuration loading pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping

from platformdirs import user_config_dir

from .schema import PodlogConfig, build_config, default_config

try:  # pragma: no cover
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

try:  # pragma: no cover
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


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
        data = yaml.safe_load(fh)
    return data or {}


def _merge(base: MutableMapping[str, Any], incoming: Mapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in incoming.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            _merge(base[key], value)  # type: ignore[index]
        else:
            base[key] = value  # type: ignore[index]
    return base


def _load_user_config() -> Dict[str, Any]:
    cfg_dir = Path(user_config_dir("podlog"))
    if not cfg_dir.exists():
        return {}
    data: Dict[str, Any] = {}
    for filename in ("podlog.toml", "podlog.yaml", "podlog.yml"):
        payload = _load_toml(cfg_dir / filename) if filename.endswith(".toml") else _load_yaml(cfg_dir / filename)
        if payload:
            data = _merge(data or {}, payload)
    return data


def _load_local_config() -> Dict[str, Any]:
    cwd = Path.cwd()
    data: Dict[str, Any] = {}
    for filename in ("podlog.toml", "podlog.yaml", "podlog.yml"):
        path = cwd / filename
        payload = _load_toml(path) if filename.endswith(".toml") else _load_yaml(path)
        if payload:
            data = _merge(data or {}, payload)
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
    return podlog if isinstance(podlog, Mapping) else {}


def _coerce_value(value: str) -> Any:
    lowered = value.strip()
    if lowered.lower() in {"true", "false"}:
        return lowered.lower() == "true"
    try:
        return int(lowered)
    except ValueError:
        try:
            return float(lowered)
        except ValueError:
            pass
    if lowered.startswith("[") or lowered.startswith("{"):
        try:
            return json.loads(lowered)
        except json.JSONDecodeError:
            pass
    return value


def _env_config() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for env_key, raw_value in os.environ.items():
        if not env_key.startswith(_ENV_PREFIX):
            continue
        path = env_key[len(_ENV_PREFIX) :].split("__")
        target = data
        for segment in path[:-1]:
            seg = segment.lower()
            target = target.setdefault(seg, {})  # type: ignore[assignment]
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
