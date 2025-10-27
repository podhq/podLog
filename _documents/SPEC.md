# podLog – Public Package User Story & Engineering Spec (v0.3 Draft)

> This document combines the existing working source (“old-source.md”) and the package design/roadmap (“pod_log_design_spec_roadmap_v_0.md”), plus additional guidance to help an AI code generator (Codex) scaffold a production-ready, standalone logging package. **No full source code** is requested here—only structure, interfaces, and contracts.

---

## 1) Product Overview

**Goal:** Build a **standalone, production-grade Python logging package** that is fully compatible with `logging` in the standard library, with smart defaults, context-aware logging, multiple output formats (text/JSONL/logfmt/CSV), rotation/retention, and optional async dispatch. The package will be **independent**, **public**, and maintained under an **organization** GitHub repo. It is **not** related to any other private projects.

**Audience:** Application and library developers who want structured, contextual, and reliable logs out-of-the-box.

**Primary Outcomes:**
- Simple API: `configure()`, `get_logger()`, `get_context_logger(...)`.
- Deterministic log paths with date folders; decoupled filename vs. format.
- Clean support for context + extras, with readable text and structured JSONL.
- Safe, testable rotation/retention behavior with clear configuration.

---

## 2) In-Scope & Out-of-Scope

**In-Scope**
- A single installable package (tentative name: **`podlog`**) with **only** the `/core` implementation included from the legacy/demo codebase. The previous `main.py` was a **demo harness** and **must not** ship inside `src/`.
- Formatters: text, JSONL, logfmt, CSV.
- Handlers: console, rotating file (size/time), optional syslog/GELF/OTLP adapters.
- Context-aware logging adapter and filters.
- Queue-based async logging via `QueueHandler/QueueListener`.
- Configuration via `pyproject.toml` under `[tool.podlog]` with overrides via env and runtime.
- Documentation set for public GitHub and PyPI.

**Out-of-Scope**
- Application-specific “strategy” or business logic demos.
- Shipping any demo/testing program as part of the library artifact.
- Proprietary integrations not covered by standard logging or optional adapters.

---

## 3) Current Capabilities to Preserve (from the legacy working code)

The existing core demonstrates:
- **Context-aware adapter** that keeps a persistent context map, supports `set_context(...)`, `add_context(...)`, `add_extra(...)`, and injects a context string plus merged extras into `LogRecord` via the standard `extra` field. Text formatters can render `%(context)s` and a rendered `extra_kvs`. JSON formatters serialize all non-standard attributes into `extra`.
- **Daily date-folder handling**: emitting to `logs/YYYY/MM/DD/<filename>` with safe rollover after midnight when the file path changes.
- **Filters**: allow exact level, min level, or a set of allowed levels.
- **Multiple sinks**: human-readable text, JSON for audit/trace, debug-extra with key=val pairs, alerts, and error-only sinks.

> These behaviors must be carried forward into the package architecture and adapted to the new configuration and naming scheme.

---

## 4) Package Name & Distribution

- **Name:** `podlog` (lowercase). If name is unavailable on PyPI, fallback to `pod-log` or `pod_logging`.
- **Distribution:** `pyproject.toml` with PEP 621 metadata; build wheels and sdists.
- **License:** MIT (unless the org prefers another permissive license).

---

## 5) High-Level Architecture

```
podlog/
  ├─ src/
  │   └─ podlog/
  │       ├─ __init__.py
  │       ├─ version.py
  │       ├─ api.py                  # configure(), get_logger(), get_context_logger()
  │       ├─ config/
  │       │   ├─ __init__.py
  │       │   ├─ loader.py           # discovery & merge: kwargs > env > pyproject > local files > user config > defaults
  │       │   └─ schema.py           # dataclasses / pydantic-like validation + defaults
  │       ├─ core/
  │       │   ├─ manager.py          # LoggerManager builds loggers/handlers/formatters
  │       │   ├─ context.py          # ContextAdapter + ContextFilter
  │       │   ├─ levels.py           # TRACE=5 registration + helpers
  │       │   ├─ registry.py         # plugin registry for handlers/formatters
  │       │   └─ validation.py       # user-friendly config errors
  │       ├─ handlers/
  │       │   ├─ console.py
  │       │   ├─ file_rotating.py    # size/time rotation, retention, gzip
  │       │   ├─ syslog.py           # optional
  │       │   ├─ gelf_udp.py         # optional
  │       │   ├─ otlp.py             # optional
  │       │   ├─ queue_async.py      # QueueHandler + QueueListener
  │       │   └─ null.py             # drop sink
  │       ├─ formatters/
  │       │   ├─ text.py
  │       │   ├─ jsonl.py
  │       │   ├─ logfmt.py
  │       │   └─ csvfmt.py
  │       └─ utils/
  │           ├─ paths.py            # base dir + date folders (flat/nested), filename synthesis
  │           └─ time.py
  ├─ pyproject.toml
  ├─ README.md
  ├─ FEATURES.md
  ├─ USAGE.md
  ├─ CONFIG.md
  ├─ CONTRIBUTING.md
  ├─ CODE_OF_CONDUCT.md
  ├─ SECURITY.md
  ├─ CHANGELOG.md
  ├─ .editorconfig
  ├─ .gitignore
  ├─ .pre-commit-config.yaml
  ├─ tests/
  └─ examples/
```

**Important migration rule for Codex:** Only the **`/core`** implementation from the legacy demo is relevant for the package internals. Any **`main.py`** from the old repo was a **demo-only** file for logger testing and **must not** be part of `src/` in the package. Create separate example scripts under `examples/` if needed.

---

## 6) Public API (stable)

```py
import podlog as pl

# 1) Configure from discovered files/env; optional runtime overrides dict
pl.configure(overrides: dict | None = None) -> None

# 2) Get a standard logger (stdlib logging.Logger)
pl.get_logger(name: str)

# 3) Get a context-aware logger
pl.get_context_logger(name: str, **context_kv)  # returns a LoggerAdapter-like object
```

**Contracts**
- `get_context_logger` returns an adapter that supports:
  - `set_context(dict_or_str)` – replace persistent context
  - `add_context(**kv)` – merge keys
  - `clear_extra()` – clear buffered extras
  - `add_extra(*args, **kwargs)` – collect variables/extras by explicit names or inferred variable names
  - standard `.debug/.info/.warning/.error/.critical` methods, plus `.trace(...)` if enabled
- The adapter **must** inject `context` and merged extras via `kwargs["extra"]` so they become attributes on the `LogRecord` and are visible to formatters. Text formatters can display `%(context)s` and a pre-rendered `%(extra_kvs)s`. JSONL formatter includes an `extra` object with all non-standard attributes.

---

## 7) Configuration Model & Precedence

1. `configure(overrides=...)`
2. Environment variables `PODLOG__...` (double underscore implies nested keys)
3. `[tool.podlog]` in `pyproject.toml`
4. `podlog.toml` / `podlog.yaml` in project root
5. User config at OS-specific config dir
6. Built-in defaults

### Key Sections

**[tool.podlog.paths]**
- `base_dir`: default `"logs"`
- `date_folder_mode`: `"flat"` → `logs/YYYY-MM-DD/` or `"nested"` → `logs/YYYY/MM/DD/`
- `date_format`: used when `flat`

**[tool.podlog.logging]**
- `propagate`, `disable_existing_loggers`, `force_config`, `capture_warnings`, `incremental`
- `queue_listener` config is under `async` section

**[tool.podlog.levels]**
- `root`, `enable_trace`, and per-logger named levels

**[tool.podlog.handlers]**
- `enabled` list with per-handler blocks
- File rotation: `size` or `time`, with retention + optional gzip

**[tool.podlog.formatters]**
- `text`, `jsonl`, `logfmt`, `csv` with custom maps/columns

**[tool.podlog.context]**
- `enabled`, allowed keys (for validation/hardening)

**[tool.podlog.async]**
- `use_queue_listener`, `queue_maxsize`, `flush_interval_ms`, `graceful_shutdown_timeout_s`

---

## 8) Filename/Format Policy & Paths

- **Format is chosen by config; not implied by filename.** Extensions like `.log`, `.jsonl`, `.csv` are conventional only.
- Full path synthesis: `/{base_dir}/{date-folder}/{filename}` with `flat|nested` date-folder rules.
- Rotation happens **inside the date folder** with numeric suffixes; archives may be gzip-compressed.

---

## 9) Rotation, Retention & Cleanup

- **Size-based** and **time-based** rotation via stdlib handlers.
- **Retention**: background worker deletes old archives per policy.
- Time-based rotation should align with `when="midnight"` or other modes, configurable per handler.

---

## 10) Levels & Filters

- Support a custom `TRACE` level (e.g., levelno 5) registered on import when enabled.
- Filters supported: **ExactLevel**, **MinLevel**, **LevelsAllow**.
- Routing matrix optionally maps levels → handlers.

---

## 11) Context & Extras Semantics

- Context is an ordered, stable `key=value` string for text outputs.
- Extras buffer aggregates structured state, merged with per-call `extra`.
- JSONL formatter outputs full `extra` object (or a whitelist when configured).
- Text `debug-extra` output shows `key=value` pairs for rapid diagnostics.

---

## 12) Async / Queue Mode

- Optional `QueueHandler/QueueListener` with bounded queue (`queue_maxsize`) and graceful shutdown.
- Flush interval and shutdown timeout configurable.

---

## 13) Repository Tasks for Codex (Do This Exactly)

1) **Create repository scaffold** with the layout in §5.
2) Implement **`api.py`** with `configure`, `get_logger`, `get_context_logger`.
3) Implement **config loader** (env + files + runtime overrides) and **schema** with defaults and validation.
4) Implement **core manager** to build handlers/formatters/loggers from config.
5) Port and adapt the **context-aware adapter**, **filters**, and **daily/date folder path logic** into the new architecture (see §3, §11). Ensure context and extras are attached **inside** `kwargs["extra"]` for stdlib compatibility.
6) Implement **formatters**: text, jsonl, logfmt, csv with the documented fields and options.
7) Implement **handlers**: console, file_rotating (size/time) with retention + gzip; optional syslog/GELF/OTLP; queue_async wrapper.
8) Implement **levels** (TRACE) and per-logger level config.
9) Add **tests** (pytest):
   - config precedence and validation
   - path/date-folder synthesis (flat/nested)
   - rotation & retention behavior
   - context + extras visibility in text and JSONL outputs
   - filters and routing
   - queue mode graceful shutdown
10) Add **examples/** scripts (not installed as package) showing quickstart and context logging.
11) Write GitHub docs: README, FEATURES, USAGE, CONFIG, contributing, code of conduct, security, changelog.
12) Set up **CI**: ruff/black, pytest + coverage, build wheels on tag, publish to TestPyPI → PyPI.

**Critical packaging rule:** Do **not** include any legacy `main.py` demo in `src/`. If a demo is needed, place it under `examples/` only. The package’s public API lives in `api.py` and `__init__.py`.

---

## 14) Acceptance Criteria

- `pip install` of the built wheel exposes `podlog.configure`, `podlog.get_logger`, `podlog.get_context_logger`.
- Creating a context logger and logging at different levels produces:
  - Text file with `%(context)s` and message
  - A JSONL file with a top-level `extra` object capturing non-standard attributes
  - Optional debug-extra text showing `key=value` pairs
- Date folders are created as per config; rotation and retention behave as configured and do not cross date-folder boundaries.
- Enabling `TRACE` results in usable `.trace(...)` calls and/or mapping `.debug` to TRACE sinks when configured.
- Queue mode can be toggled; shutdown is graceful with no lost records in normal operation.

---

## 15) Documentation Plan (GitHub)

- **README.md:** What/Why/Install/Quickstart
- **FEATURES.md:** Major features list
- **USAGE.md:** API examples and scenarios
- **CONFIG.md:** Full TOML schema and examples
- **CONTRIBUTING.md:** Dev setup, lint/test, PR flow, semantic commits
- **CODE_OF_CONDUCT.md**, **SECURITY.md**, **CHANGELOG.md**

---

## 16) Testing Matrix (pytest)

- Unit tests for each formatter/handler
- Integration tests that load config and emit logs to tmp dir; verify files, rotation, retention
- Property tests for context merging and `extra` serialization
- Performance sanity tests for queue mode (bounded queue, backpressure)

---

## 17) Additional Recommendations

- Provide a **sampling** and **redaction** hook (roadmap), e.g., to mask API keys and emails.
- Add a **plugin registry** to allow external formatters/handlers.
- Publish **benchmarks** comparing console vs. file vs. queue modes.

---

## 18) Example Minimal `pyproject.toml` (for docs)

```toml
[tool.podlog.paths]
base_dir = "logs"
date_folder_mode = "flat"

[tool.podlog.handlers]
enabled = ["console", "app_file"]

[tool.podlog.handlers.console]
type = "console"
level = "INFO"
formatter = "text_default"

[tool.podlog.handlers.app_file]
type = "file_rotating"
level = "DEBUG"
formatter = "text_rich"
filename = "app.log"
rotation = { mode = "size", max_bytes = 5000000, backup_count = 10 }
retention = { days = 14, compress = true }

[tool.podlog.formatters.text_default]
type = "text"
fmt = "%(asctime)s [%(levelname)s] %(name)s | %(message)s"

[tool.podlog.formatters.text_rich]
type = "text"
fmt = "%(asctime)s [%(levelname)s] %(name)s [%(context)s] :: %(message)s"
```

---

## 19) Notes to Codex (Execution Plan)

- Generate the repo skeleton and implement modules per sections above.
- Ensure **no full demo app** ships inside the package; examples must live under `examples/`.
- Favor composition and dependency injection inside `core/manager.py` to keep the API thin.
- When porting legacy logic, keep the `extra` injection strictly inside `kwargs["extra"]` for stdlib compatibility and formatter access.
- Prepare initial unit tests for CI and verify Windows/macOS/Linux filesystem path handling for date folders and gzip.

---

**End of Spec**

