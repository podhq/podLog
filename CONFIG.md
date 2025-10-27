# Configuration reference

podlog consumes configuration from multiple layers. The effective structure is a dictionary equivalent to the following TOML
schema. Each section is optional and merges with defaults.

## `[paths]`

| Key                | Type   | Default    | Description |
|--------------------|--------|------------|-------------|
| `base_dir`         | str    | `"logs"`   | Root directory for all log files. |
| `date_folder_mode` | str    | `"nested"` | `"nested"` → `logs/YYYY/MM/DD/`, `"flat"` → `logs/YYYY-MM-DD/`. |
| `date_format`      | str    | `%Y-%m-%d` | Used when `date_folder_mode = "flat"`. |

## `[formatters]`

Formatters are grouped by kind. The key after the kind names the formatter (`kind.name`).

```toml
[tool.podlog.formatters.text]
default.show_extras = true
app = { fmt = "%(message)s", datefmt = "%H:%M:%S" }

[tool.podlog.formatters.jsonl]
audit = { whitelist = ["user_id"] }

[tool.podlog.formatters.logfmt]
structured = { keys = ["context", "extra_kvs"] }

[tool.podlog.formatters.csv]
report = { fields = ["ts", "level", "message"], include_header = true }
```

## `[filters]`

| Type    | Parameters                         | Notes |
|---------|------------------------------------|-------|
| `exact` | `level`                            | Only emit records at the exact level. |
| `min`   | `level`                            | Emit records at or above the level. |
| `levels`| `levels` (list of str/int levels)  | Allow-list arbitrary level numbers/names. |

## `[handlers]`

Each handler is configured under `tool.podlog.handlers.<name>` and must appear in the `enabled` array. Common options:

- `type`: `console`, `file`, `syslog`, `gelf_udp`, `otlp`, or `null`.
- `formatter`: name defined in `[formatters]` (`text.default`, `jsonl.audit`, ...).
- `level`: minimum level for the handler.
- `filters`: optional list of filter names.
- `filename`: required for `file` handlers (relative to the resolved date folder).
- `rotation.size`: `max_bytes`, `backup_count`.
- `rotation.time`: `when`, `interval`, `backup_count`, `utc`.
- `retention`: `max_files`, `max_days`, `compress`.
- `encoding`, `delay`.

Example:

```toml
[tool.podlog.handlers]
enabled = ["console", "app_file", "alerts"]

[tool.podlog.handlers.console]
type = "console"
formatter = "text.default"
stream = "stdout"

[tool.podlog.handlers.app_file]
type = "file"
filename = "app.log"
formatter = "text.default"
rotation.size.max_bytes = 10485760
rotation.size.backup_count = 7
retention.max_days = 14
retention.compress = true

[tool.podlog.handlers.alerts]
type = "gelf_udp"
host = "log.local"
port = 12201
```

## `[logging]`

- `root.level`: default level (falls back to `[levels].root`).
- `root.handlers`: list of handler names attached to the root logger.
- `loggers.<name>.level`: per-logger level.
- `loggers.<name>.handlers`: handler names for the logger.
- `loggers.<name>.propagate`: whether the logger propagates to its parent.
- `disable_existing_loggers`: disable loggers not explicitly configured.
- `capture_warnings`: redirect `warnings` module output to logging.

## `[levels]`

- `root`: base level used when `logging.root.level` is omitted.
- `enable_trace`: set to `true` to register the TRACE level (numeric level 5).
- `overrides`: mapping of logger name → level (applied even if the logger is not explicitly configured).

## `[context]`

- `enabled`: toggle context adapter enforcement when requesting context loggers.
- `allowed_keys`: if non-empty, restricts context defaults to these keys.

## `[async]`

- `use_queue_listener`: enable async dispatch.
- `queue_maxsize`: maximum queue length (`0` for unbounded).
- `flush_interval_ms`: best-effort handler flush interval.
- `graceful_shutdown_timeout_s`: maximum wait for flush thread.

## Example `pyproject.toml`

```toml
[tool.podlog.paths]
base_dir = "logs"
date_folder_mode = "nested"

[tool.podlog.formatters.text]
default.show_extras = true

[tool.podlog.handlers]
enabled = ["console", "file"]

[tool.podlog.handlers.console]
type = "console"
formatter = "text.default"
stream = "stderr"

[tool.podlog.handlers.file]
type = "file"
filename = "app.log"
formatter = "text.default"
rotation.size.max_bytes = 1048576
rotation.size.backup_count = 5
retention.max_days = 7

[tool.podlog.logging.root]
level = "INFO"
handlers = ["console", "file"]

[tool.podlog.async]
use_queue_listener = true
queue_maxsize = 500
flush_interval_ms = 100
```
