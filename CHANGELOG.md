# Changelog

## v0.1.0 (2025-10-27)

- Initial public release of podlog.
- Context-aware logging adapter with extras buffering and TRACE level support.
- Structured formatters: text, JSONL, logfmt, and CSV.
- Handler suite: console, rotating file, syslog, GELF UDP, OTLP (optional), queue async, null.
- Declarative configuration loader with precedence (runtime, env, pyproject, local files, user config, defaults).
- Rotation and retention policies with gzip compression and daily date folders.
- pytest test suite covering configuration, formatting, rotation, filters, and async queue lifecycle.
