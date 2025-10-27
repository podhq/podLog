# Usage guide

## 1. Configuring podlog

`podlog.configure()` discovers configuration sources automatically. You can override or provide an in-memory configuration by
passing a dictionary that mirrors the TOML schema.

```python
import podlog

podlog.configure(
    {
        "paths": {"base_dir": "logs", "date_folder_mode": "nested"},
        "formatters": {
            "text": {"app": {"show_extras": True}},
            "jsonl": {"audit": {}},
        },
        "handlers": {
            "enabled": ["text", "json"],
            "text": {
                "type": "file",
                "filename": "app.log",
                "formatter": "text.app",
                "level": "INFO",
            },
            "json": {
                "type": "file",
                "filename": "audit.jsonl",
                "formatter": "jsonl.audit",
                "level": "INFO",
                "rotation": {"size": {"max_bytes": 1_000_000, "backup_count": 5}},
            },
        },
        "logging": {"root": {"level": "INFO", "handlers": ["text", "json"]}},
    }
)
```

Environment variables can override nested keys using double underscores, e.g. `PODLOG__PATHS__BASE_DIR=/var/log/app`.

## 2. Working with context loggers

```python
log = podlog.get_context_logger("orders", service="checkout", region="us-east")
log.add_context(env="prod")
log.add_extra(order_id=1234, total=57.30)
log.info("order processed")
```

- `set_context()` replaces the persistent context dictionary.
- `add_context()` merges additional keys.
- `add_extra()` accepts keyword arguments or positional variables, inferring names from the caller’s frame.
- `clear_extra()` drops buffered extras after use.

These helpers ensure `LogRecord.context` and `LogRecord.extra_kvs` exist for all formatters.

## 3. Filters and routing

Handlers can reference filters defined in configuration:

```toml
[tool.podlog.filters]
warn_only.type = "min"
warn_only.level = "WARNING"

errors_only.type = "levels"
errors_only.levels = ["ERROR", "CRITICAL"]

[tool.podlog.handlers]
enabled = ["warnings", "errors"]

[tool.podlog.handlers.warnings]
type = "file"
filename = "warnings.log"
formatter = "text.default"
filters = ["warn_only"]

[tool.podlog.handlers.errors]
type = "file"
filename = "errors.log"
formatter = "text.default"
filters = ["errors_only"]
```

## 4. Async queue dispatch

Enable the queue listener in the `async` section:

```toml
[tool.podlog.async]
use_queue_listener = true
queue_maxsize = 1000
flush_interval_ms = 250
graceful_shutdown_timeout_s = 2.0
```

Each enabled handler is wrapped with a blocking `QueueHandler`; a background `QueueListener` drains records and flushes handlers at
the configured interval. The queue coordinator shuts down gracefully when `GLOBAL_MANAGER.shutdown()` is invoked (called implicitly
when reconfiguring via `podlog.configure`).

## 5. Formatter options

- `text`: `show_extras`, `fmt`, `datefmt`
- `jsonl`: `whitelist`, `drop_fields`, `datefmt`
- `logfmt`: `keys`, `datefmt`
- `csv`: `fields`, `extra_fields`, `include_header`, `datefmt`

See [CONFIG.md](CONFIG.md) for full option descriptions and examples.
