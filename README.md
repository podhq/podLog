# podlog

**podlog** is a production-grade logging toolkit for Python that layers a modern configuration system, structured formatters, and
sane defaults on top of the standard library's `logging` package. It keeps your logs contextual, routable, and safe to operate
across multiple destinations with minimal boilerplate.

## Key features

- Context-aware adapters that automatically merge persistent context and per-call extras into every `LogRecord`.
- Text, JSON Lines, logfmt, and CSV formatters with consistent field rendering.
- Daily date-folder aware file handlers with size/time rotation, retention policies, and optional gzip compression.
- Optional async dispatch via `QueueHandler`/`QueueListener` to protect critical paths from I/O stalls.
- Configurable filters (exact, minimum, allow-list) and a handler registry for console, file, syslog, GELF, OTLP, and null sinks.
- Declarative configuration discovery from runtime overrides, environment variables, project files, user config, and defaults.

See [FEATURES.md](FEATURES.md) for a deeper tour of the platform capabilities.

## Installation

```bash
pip install podlog
```

The package targets Python 3.9 and newer.

## Quickstart

```python
import podlog

# Discover configuration from pyproject.toml/env/user config and override at runtime
podlog.configure(
    {
        "paths": {"base_dir": "logs", "date_folder_mode": "nested"},
        "handlers": {
            "enabled": ["app"],
            "app": {
                "type": "file",
                "filename": "application.log",
                "formatter": "text.default",
                "level": "INFO",
            },
        },
        "logging": {"root": {"level": "INFO", "handlers": ["app"]}},
    }
)

log = podlog.get_context_logger("demo", service="billing", request_id="req-123")
log.add_extra(customer_id="cust-456")
log.info("invoiced customer")
```

Logs are emitted under `logs/YYYY/MM/DD/application.log` (or flat folders if configured) and include the context fields so that
formatters, structured exporters, and search tools can reason about your application state.

## Configuration

podlog reads configuration in the following precedence order:

1. Runtime overrides passed to `configure()`
2. Environment variables prefixed with `PODLOG__`
3. `[tool.podlog]` table in `pyproject.toml`
4. `podlog.toml` or `podlog.yaml` in the project directory
5. User config under the OS-specific config directory
6. Built-in defaults

The full schema and examples live in [CONFIG.md](CONFIG.md).

## Additional documentation

- [FEATURES.md](FEATURES.md) – high-level capability overview
- [USAGE.md](USAGE.md) – API walkthroughs, context helpers, filters, and async dispatch
- [CONFIG.md](CONFIG.md) – configuration schema reference with TOML examples
- [examples/](examples/) – runnable snippets illustrating typical workflows

## Development

Clone the repository, create a virtual environment, and install the development dependencies:

```bash
pip install -e .[otlp]
pip install -r requirements-dev.txt  # if you maintain a dev requirements file
pre-commit install
pytest
```

`pre-commit` enforces formatting and linting, while `pytest` exercises the full test suite.

## License

This project is released under the [MIT License](LICENSE).
