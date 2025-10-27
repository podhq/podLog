# podLog – Design Spec & Roadmap (v0.2)

> **Goal**: A standalone, production-grade logging package for Python projects (FluxBot and beyond), highly configurable via files (pyproject.toml / podlog.toml / YAML), with clean defaults, stdlib-logging compatibility, and ready for PyPI + GitHub collaboration.

---

## ✅ Key Decisions (incorporating feedback)

1) **Filename & format decoupling**  
   Filenames **do not encode format**. Example: `trace.log` (text), `trades.jsonl` (JSON Lines), `metrics.csv` (CSV), regardless of content formatter. Extension is conventional, but **format is chosen in config**.

2) **Stdlib logging compatibility settings**  
   We surface common `logging` knobs under `[tool.podlog.logging]` with sensible defaults:
   - `propagate` (bool, default: `false` for named loggers created by podLog)
   - `disable_existing_loggers` (bool, default: `false`)
   - `force_config` (bool, default: `false`) – if `true`, podLog will reconfigure root handlers
   - `capture_warnings` (bool, default: `true`) – redirect `warnings` to logging
   - `incremental` (bool, default: `false`) – incremental updates where supported
   - `queue_listener` settings kept separate (see async section)

3) **Additional output formats (formatters)**  
   Beyond Text and JSONL, podLog ships:
   - `text` – human-readable pattern
   - `jsonl` – structured JSON per line
   - `logfmt` – key=value pairs (Heroku-style)
   - `csv` – columnar CSV header + rows
   (Optional adapters for Syslog/GELF/OTLP are provided as **handlers**, not formatters.)

4) **Docs for GitHub**  
   We ship comprehensive public docs: `README.md`, `FEATURES.md`, `USAGE.md`, `CONFIG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `SECURITY.md`. See outlines below.

5) **Rolling/Rotation**  
   Built-in **size-based** and **time-based** rotation via stdlib (`RotatingFileHandler`, `TimedRotatingFileHandler`). Rotation happens **inside the date folder**. Numeric suffix `.1`, `.2`, ... is used by default; optional gzip compression for rotated archives. Retention policy via cleanup worker.

---

## Package Layout

```
podlog/
  ├─ src/
  │   └─ podlog/
  │       ├─ __init__.py
  │       ├─ version.py
  │       ├─ api.py                  # configure(), get_logger(), get_context_logger()
  │       ├─ config/
  │       │   ├─ __init__.py
  │       │   ├─ loader.py           # discover & merge config from: kwargs > env > pyproject > local files > user config > defaults
  │       │   └─ schema.py           # dataclasses / pydantic-like validation + defaults
  │       ├─ core/
  │       │   ├─ manager.py          # LoggerManager (singleton), builds loggers/handlers/formatters
  │       │   ├─ context.py          # ContextAdapter + ContextFilter (symbol, timeframe, step, ...)
  │       │   ├─ levels.py           # TRACE=5 registration + helper
  │       │   ├─ registry.py         # plugin registry for handlers/formatters
  │       │   └─ validation.py       # config errors with actionable messages
  │       ├─ handlers/
  │       │   ├─ console.py
  │       │   ├─ file_rotating.py    # size/time rotation, retention, gzip, numeric suffixes
  │       │   ├─ syslog.py           # optional (platform dependent)
  │       │   ├─ gelf_udp.py         # optional (Graylog)
  │       │   ├─ otlp.py             # optional (OpenTelemetry logs exporter)
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

> **Note**: No demo/test classes inside `src/`. Tests live in `tests/` only.

---

## Configuration Model (TOML) – Overview

### Sources & precedence
1. Runtime overrides via `podlog.configure(overrides: dict)`  
2. Environment variables `PODLOG__...` (double underscores `__` → nested keys)  
3. `[tool.podlog]` in `pyproject.toml`  
4. `podlog.toml` / `podlog.yaml` in project root  
5. User config: `~/.config/podlog/config.toml` (Linux/macOS) or `%APPDATA%/podlog/config.toml` (Windows)  
6. Built-in defaults

### Paths & Date folders
```toml
[tool.podlog.paths]
base_dir = "logs"
date_folder_mode = "flat"          # flat | nested
date_format = "%Y-%m-%d"           # only used when flat
nested_order = ["year","month","day"]
```
- **flat** → `logs/2025-10-27/`
- **nested** → `logs/2025/10/27/`

### Stdlib logging compatibility
```toml
[tool.podlog.logging]
propagate = false
disable_existing_loggers = false
force_config = false
capture_warnings = true
incremental = false
```

### Levels
```toml
[tool.podlog.levels]
root = "INFO"
enable_trace = true

[tool.podlog.levels.named]
strategy = "DEBUG"
exchange = "INFO"
```

### Handlers (enable/disable & per-handler setup)
```toml
[tool.podlog.handlers]
enabled = ["console", "app_file", "json_trades", "csv_metrics"]

[tool.podlog.handlers.console]
type = "console"
level = "INFO"
formatter = "text_default"
stderr = true

[tool.podlog.handlers.app_file]
type = "file_rotating"
level = "DEBUG"
formatter = "text_rich"
filename = "app.log"                      # filename only; podLog builds full path in date folder
rotation = { mode = "size", max_bytes = 5000000, backup_count = 10 }
retention = { days = 14, compress = true }

[tool.podlog.handlers.json_trades]
type = "file_rotating"
level = "INFO"
formatter = "jsonl_struct"
filename = "trades.jsonl"
rotation = { mode = "time", when = "midnight", interval = 1, backup_count = 7 }
retention = { days = 30, compress = true }

[tool.podlog.handlers.csv_metrics]
type = "file_rotating"
level = "INFO"
formatter = "csv_metrics"
filename = "metrics.csv"
rotation = { mode = "size", max_bytes = 2000000, backup_count = 5 }
retention = { days = 7, compress = false }
```

### Routing (optional)
```toml
[tool.podlog.routing]
json_trades = ["INFO","WARNING","ERROR","CRITICAL"]
app_file   = ["TRACE","DEBUG","INFO","WARNING","ERROR","CRITICAL"]
```

### Formatters
```toml
[tool.podlog.formatters.text_default]
type = "text"
fmt = "%(asctime)s [%(levelname)s] %(name)s | %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"

[tool.podlog.formatters.text_rich]
type = "text"
fmt = "%(asctime)s [%(levelname)s] %(name)s [%(context)s] :: %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"

[tool.podlog.formatters.jsonl_struct]
type = "jsonl"
map = { ts="timestamp", lvl="level", log="logger", msg="message" }
include_extra = true

[tool.podlog.formatters.csv_metrics]
type = "csv"
# columns define CSV header and the order of fields
columns = ["timestamp","level","logger","message","context","symbol","timeframe","step"]
include_extra = false

[tool.podlog.formatters.logfmt_default]
type = "logfmt"
# template defines which keys are included; order preserved
keys = ["timestamp","level","logger","message","context"]
```

### Context & Validation
```toml
[tool.podlog.context]
enabled = true
allowed_keys = ["symbol","timeframe","step","run_id","order_id"]
```

### Async / Queue
```toml
[tool.podlog.async]
use_queue_listener = true
queue_maxsize = 10000
flush_interval_ms = 200
graceful_shutdown_timeout_s = 5
```

### Environment overrides (examples)
```
PODLOG__LEVELS__ROOT=DEBUG
PODLOG__HANDLERS__APP_FILE__RETENTION__DAYS=60
PODLOG__PATHS__DATE_FOLDER_MODE=nested
```

---

## Filenames, Extensions & Paths – Policy
- **Format never appears in the filename** (your request #1).  
- The **extension is conventional** (e.g., `.log`, `.jsonl`, `.csv`) and **does not drive the formatter**; the formatter is chosen by config.  
- podLog composes full path as:  
  `/{base_dir}/{date-folder}/<filename>`  
  with date folder built per `flat|nested` rules.

---

## Rotation & Retention
- **Size-based** (`RotatingFileHandler`): rolls when `max_bytes` exceeded; numeric suffixes `.1`, `.2`, ... inside the **same date folder**. Optional gzip compression for archived files.
- **Time-based** (`TimedRotatingFileHandler`): roll on `when` ("midnight", "H", etc.) with `interval`. Optional gzip compression.
- **Retention**: background cleanup removes archives older than `retention.days`.

> Example rolled files (size mode):
```
logs/2025-10-27/app.log
logs/2025-10-27/app.log.1.gz
logs/2025-10-27/app.log.2.gz
```

---

## API Surface (consumer)
```python
import podlog as pl

# 1) Auto-discover config from files/env; you may pass runtime overrides
pl.configure()

# 2) Get regular or context logger
log = pl.get_logger("strategy")
ctx = pl.get_context_logger("strategy", symbol="BTC/USDT", timeframe="15m")

log.info("App started")
ctx.info("Signal accepted", extra={"context": {"step": "validate"}})
ctx.trace("ATR computed")  # enabled if TRACE active
```

---

## GitHub Docs – Outlines

**README.md**
- What is podLog?
- Key features
- Quickstart
- Install (`pip install podlog`)
- Basic configuration (pyproject.toml snippet)
- Example usage
- Links to `USAGE.md`, `CONFIG.md`, `FEATURES.md`

**FEATURES.md**
- Multi-source configuration & precedence
- Date folders (flat/nested) + custom formats
- Text/JSONL/CSV/logfmt formatters
- Rotation & retention (size/time + gzip)
- Queue-based async logging
- TRACE level support
- Context-aware logging
- Optional handlers: Syslog, GELF, OTLP

**USAGE.md**
- API examples (`configure`, `get_logger`, `get_context_logger`)
- Adding per-module levels
- Routing to specific handlers
- Using environment overrides
- Performance notes (queue, sampling)

**CONFIG.md**
- Full TOML schema (with defaults)
- All handler/formatter options
- Filename/path rules
- Rotation/retention matrix
- Validation errors & troubleshooting

**CONTRIBUTING.md**
- Dev setup, `uv/poetry` or `pipx`, pre-commit, ruff/black
- Tests: pytest
- Branching strategy & PR guidelines
- Semantic commit examples

**CHANGELOG.md**
- Keep a Changelog format, SemVer

**SECURITY.md**
- How to report vulnerabilities

**CODE_OF_CONDUCT.md**
- Contributor Covenant

---

## Defaults (Best-Practice)
- `paths`: `base_dir="logs"`, `date_folder_mode="flat"`, `date_format="%Y-%m-%d"`
- `levels`: `root=INFO`, `enable_trace=true`
- Handlers enabled by default: `console(INFO, text_default)` + `app_file(DEBUG, text_rich, size 5MB×10, retention 14d gzip)` + `json_trades(INFO, jsonl_struct, midnight rotation, retention 30d)`
- Context enabled with recommended keys
- Queue listener enabled

---

## Roadmap (MVP → v0.2 → v0.3)

**MVP (v0.1.0)**
- [x] Core: configure/load/merge schema
- [x] Levels: TRACE
- [x] Formatters: text, jsonl
- [x] Handlers: console, file_rotating (size/time), retention (gzip)
- [x] Paths & date folders (flat/nested)
- [x] Context adapter + filter
- [x] Async queue listener
- [x] Stdlib compatibility block

**v0.2.0 (this spec)**
- [x] Filenames independent from format
- [x] Additional formatters: csv, logfmt
- [x] Optional handlers: syslog, gelf_udp, otlp (behind extra)
- [x] Docs set for GitHub (outlined)
- [x] Cleanup worker for retention

**v0.3.x**
- [ ] Redaction/masking rules (PII, API keys)
- [ ] Sampling controls per level/handler
- [ ] Structured context schemas per logger
- [ ] OTLP exporter test matrix (OTel collector)
- [ ] Benchmarks & perf guide

---

## Quality Gates (CI/CD)
- Lint: ruff + black
- Tests: pytest + coverage
- Pre-commit hooks
- Wheels build on tag; publish to TestPyPI → PyPI
- Release notes from CHANGELOG

---

## Example Minimal pyproject.toml
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

**Status**: Ready to scaffold code per this spec. If you sign off, next step is generating the repository skeleton and initial modules. 

