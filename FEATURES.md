# podlog features

## Contextual logging

- Persistent context dictionaries, string parsing, and runtime extras merged into the `LogRecord.extra` mapping.
- Automatically rendered `context` and `extra_kvs` attributes usable by all formatters.
- Adapter helpers: `set_context`, `add_context`, `clear_extra`, and `add_extra` with variable name inference.

## Structured outputs

- Human-readable text formatter with optional extra rendering and configurable format strings.
- JSON Lines formatter that preserves non-standard attributes inside an `extra` object with whitelist support.
- logfmt formatter for systems like Honeycomb, Grafana Loki, or vector-based pipelines.
- CSV formatter with optional headers, column selection, and automatic timestamp formatting.

## Handler ecosystem

- Console and null handlers for development and testing workflows.
- Date-aware rotating file handlers with size/time strategies, gzip compression, and retention pruning.
- Syslog (UDP/TCP/unix), GELF UDP, and optional OTLP exporter integration for centralized logging systems.
- Queue-based async coordinator that wraps handlers with blocking queue semantics to avoid record loss.

## Smart defaults & configuration

- Discovery order: runtime overrides → environment (`PODLOG__`) → `pyproject.toml` → local config files → user config dir → defaults.
- Declarative TOML schema with path, formatter, handler, filter, logging, context, and async sections.
- TRACE level (5) registration with optional enablement via configuration.
- Filters: exact level match, minimum level threshold, and allow-list for arbitrary level sets.

## Reliability & operations

- Daily date folders keep logs organized by time while allowing rotation inside each day.
- Retention policies measured in file count or days with automatic gzip compression of archives.
- Async queue shutdown waits for in-flight records and flushes handler buffers on exit.
- Test coverage for precedence rules, handler behaviors, formatting, filtering, and queue lifecycle.

Consult [USAGE.md](USAGE.md) for code examples and [CONFIG.md](CONFIG.md) for schema details.
