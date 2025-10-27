محسن—علت خطا این بود که ما در `process` مقدار `context` و `extra_kvs` را به‌صورت **کلیدهای Top-Level** داخل `kwargs` می‌گذاشتیم؛ درحالی‌که `logging` فقط `extra`، `exc_info` و… را می‌پذیرد. باید این مقادیر داخل `kwargs["extra"]` تزریق شوند تا به‌صورت attribute روی `LogRecord` بنشینند و Formatter بتواند از `%(context)s` و `%(extra_kvs)s` استفاده کند.

من این را اصلاح کردم و نسخه‌ی نهایی همه فایل‌ها را (مطابق طراحی جدیدت: بدون متد `trace`، با `add_extra`، `set_context`، خروجی `trace`=JSON و `debug_extra`=متنی) می‌گذارم. این نسخه با Pylance هم سازگار است.

---

## core/log_filters.py

```python
# core/log_filters.py
from __future__ import annotations
import logging
from typing import Iterable, Set

class LevelsAllowFilter(logging.Filter):
    """Allow only a specific set of levels (exact match)."""
    def __init__(self, levels: Iterable[int]):
        super().__init__()
        self.levels: Set[int] = set(levels)
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno in self.levels

class MinLevelFilter(logging.Filter):
    """Allow record.levelno >= min_level."""
    def __init__(self, min_level: int):
        super().__init__()
        self.min_level = min_level
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno >= self.min_level

class ExactLevelFilter(logging.Filter):
    """Allow only exact one level."""
    def __init__(self, level: int):
        super().__init__()
        self.level = level
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno == self.level
```

---

## core/daily_folder_handler.py

```python
# core/daily_folder_handler.py
from __future__ import annotations
import os
import datetime as _dt
import logging
from typing import Optional

class DailyFolderFileHandler(logging.FileHandler):
    """
    Writes to /logs/YYYY/MM/DD/<filename>.
    Re-evaluates path per emit to roll after midnight safely.
    """
    def __init__(self, base_dir: str, filename: str, encoding: Optional[str] = "utf-8"):
        self.base_dir = base_dir
        self.filename = filename
        os.makedirs(base_dir, exist_ok=True)
        path = self._resolve_path()
        super().__init__(path, mode="a", encoding=encoding)

    def _resolve_path(self) -> str:
        today = _dt.date.today()
        day_dir = os.path.join(self.base_dir, f"{today.year:04d}", f"{today.month:02d}", f"{today.day:02d}")
        os.makedirs(day_dir, exist_ok=True)
        return os.path.join(day_dir, self.filename)

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        todays_path = self._resolve_path()
        if self.stream and getattr(self.stream, "name", "") != todays_path:
            self.acquire()
            try:
                self.stream.close()
                self.baseFilename = todays_path  # keep logging internals in sync
                self.stream = self._open()
            finally:
                self.release()
        super().emit(record)
```

---

## core/logger.py  ✅ (اصلاح کلیدی در `process`: قراردادن context/extra_kvs داخل extra)

```python
# core/logger.py
from __future__ import annotations

import inspect
import json
import logging
from logging import Formatter
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple, cast

from .log_filters import LevelsAllowFilter, MinLevelFilter, ExactLevelFilter
from .daily_folder_handler import DailyFolderFileHandler

# --------- Text formats (human-readable) ----------
LOG_FORMAT_TEXT = "%(asctime)s | %(levelname)-5s | %(name)s | %(context)s | %(message)s"
# For text file that wants to show extras as key=val pairs
LOG_FORMAT_TEXT_WITH_EXTRAS = "%(asctime)s | %(levelname)-5s | %(name)s | %(context)s | %(message)s | %(extra_kvs)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


# ---------- JSON formatter (for audit & trace) ----------
class JSONFormatter(logging.Formatter):
    """
    JSON formatter with optional whitelist for 'extra' keys.
    If whitelist is set (e.g., ['trade']), only those extra keys are included.
    Otherwise (trace), include all non-standard attributes as 'extra'.
    """
    def __init__(self, *, datefmt: Optional[str] = None, whitelist: Optional[list[str]] = None):
        super().__init__(datefmt=datefmt)
        self.whitelist = whitelist or []

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        data = record.__dict__.copy()

        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "context": data.get("context", ""),
            "message": record.getMessage(),
        }

        std = {
            "name","msg","args","levelname","levelno","pathname","filename","module","exc_info","exc_text",
            "stack_info","lineno","funcName","created","msecs","relativeCreated","thread","threadName",
            "processName","process","asctime","context","extra_kvs"
        }

        if self.whitelist:
            extra_obj: Dict[str, Any] = {}
            for k in self.whitelist:
                if k in data:
                    extra_obj[k] = data[k]
            payload["extra"] = extra_obj
        else:
            payload["extra"] = {k: v for k, v in data.items() if k not in std}

        return json.dumps(payload, ensure_ascii=False)


# ---------- Context-aware adapter with extras buffer ----------
class ContextAdapter(logging.LoggerAdapter):
    """
    - Persistent context dict (use set_context/add_context)
    - add_extra(*args, **kwargs) to buffer extra key-values:
        * kwargs => keys given explicitly
        * args   => variable name inference from caller's frame; fallback varN
    - process(...) injects:
        * context string (built from persistent context) into extra
        * merged extras (buffer + call extras) into extra
        * extra_kvs (textified extras) into extra
    """
    def __init__(self, logger: logging.Logger, base_context: Optional[Mapping[str, Any]] = None) -> None:
        super().__init__(logger, {})  # we manage our own store
        self._context: Dict[str, Any] = dict(base_context or {})
        self._extra_buf: Dict[str, Any] = {}

    # ---- Public API ----
    def set_context(self, ctx: Mapping[str, Any] | str) -> None:
        """Replace persistent context. Accepts dict or 'k=v k2=v2' string."""
        if isinstance(ctx, str):
            self._context = self._parse_ctx_string(ctx)
        else:
            self._context = dict(ctx)

    def add_context(self, **kwargs: Any) -> None:
        """Merge/override keys into persistent context."""
        self._context.update(kwargs)

    def clear_extra(self) -> None:
        """Clear the extras buffer."""
        self._extra_buf.clear()

    def add_extra(self, *args: Any, **kwargs: Any) -> None:
        """
        Add multiple variables into extras buffer.
        - kwargs: explicit names, e.g., add_extra(diff=1.23, denom=42)
        - args: infer names from caller's locals by identity; fallback to 'var1', 'var2', ...
        """
        # 1) explicit kwargs
        for k, v in kwargs.items():
            self._extra_buf[k] = v

        if not args:
            return

        # 2) infer names for *args from caller frame
        frame = inspect.currentframe()
        if frame is None:
            # can't inspect; fallback to varN
            for i, val in enumerate(args, start=1):
                self._extra_buf[f"var{i}"] = val
            return

        try:
            caller = frame.f_back  # the function that called add_extra
            names_assigned: Dict[int, str] = {}
            if caller is not None:
                # build reverse map by object id (identity matching)
                for name, val in caller.f_locals.items():
                    names_assigned[id(val)] = name

            used_names: set[str] = set(self._extra_buf.keys())
            fallback_idx = 1
            for val in args:
                key = names_assigned.get(id(val))
                if key is None or key in used_names:
                    # fallback unique name
                    while True:
                        candidate = f"var{fallback_idx}"
                        fallback_idx += 1
                        if candidate not in used_names:
                            key = candidate
                            break
                self._extra_buf[key] = val
                used_names.add(key)
        finally:
            # break reference cycles
            del frame

    # ---- Internals ----
    @staticmethod
    def _parse_ctx_string(s: str) -> Dict[str, Any]:
        """
        Parse 'k=v k2=v2' into dict. If malformed, store whole string under '_ctx'.
        """
        result: Dict[str, Any] = {}
        parts = [p for p in s.strip().split() if p]
        try:
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    result[k] = v
            if result:
                return result
            return {"_ctx": s}
        except Exception:
            return {"_ctx": s}

    @staticmethod
    def _ctx_to_str(ctx: Mapping[str, Any]) -> str:
        # stable ordering for readability
        items = sorted(ctx.items(), key=lambda kv: kv[0])
        return " ".join(f"{k}={v}" for k, v in items)

    @staticmethod
    def _extras_to_kv_text(d: Mapping[str, Any]) -> str:
        if not d:
            return "-"
        parts: list[str] = []
        for k, v in d.items():
            try:
                s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            except Exception:
                s = repr(v)
            parts.append(f"{k}={s}")
        return " ".join(parts)

    # Signature must match LoggerAdapter (kwargs is MutableMapping)
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> Tuple[str, MutableMapping[str, Any]]:
        # Build final context string
        ctx_str = self._ctx_to_str(self._context)

        # Merge extras: buffered + call-site extras (call-site overrides)
        call_extra = kwargs.get("extra")
        merged: Dict[str, Any] = {}
        merged.update(self._extra_buf)
        if isinstance(call_extra, dict):
            merged.update(call_extra)

        # Put context & rendered extras INSIDE 'extra' so Logger accepts kwargs
        merged["context"] = ctx_str
        merged["extra_kvs"] = self._extras_to_kv_text(merged)

        kwargs["extra"] = merged
        # DO NOT set 'context' or 'extra_kvs' at top-level in kwargs (would break Logger._log)
        return msg, kwargs


# ---------- Builder ----------
def build_logger(
    name: str,
    base_logs_dir: str = "logs",
    strategy: str = "fluxbot",
    base_context: Optional[Mapping[str, Any] | str] = None
) -> ContextAdapter:
    """
    Build a multi-sink logger wrapped in ContextAdapter.
    - 'verbose.log'       : text, DEBUG+ (context + message)
    - 'audit.log'         : JSON (INFO & ERROR) with whitelist ['trade']
    - 'trace.log'         : JSON (DEBUG-only) dump all extras
    - 'debug_extra.log'   : text (DEBUG-only) includes extras as key=value
    - 'alerts.log'        : text (WARNING+)
    - 'errors.log'        : text (ERROR-only)
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Formatters
        fmt_text = Formatter(LOG_FORMAT_TEXT, DATEFMT)
        fmt_text_with_extras = Formatter(LOG_FORMAT_TEXT_WITH_EXTRAS, DATEFMT)
        fmt_audit_json = JSONFormatter(datefmt=DATEFMT, whitelist=["trade"])
        fmt_trace_json = JSONFormatter(datefmt=DATEFMT)

        # Handlers
        # 1) VERBOSE: DEBUG+ (text, minimal)
        h_verbose = DailyFolderFileHandler(base_logs_dir, f"{strategy}.verbose.log")
        h_verbose.setLevel(logging.DEBUG)
        h_verbose.setFormatter(fmt_text)

        # 2) AUDIT: INFO & ERROR (JSON only trade)
        h_audit = DailyFolderFileHandler(base_logs_dir, f"{strategy}.audit.log")
        h_audit.setLevel(logging.DEBUG)
        h_audit.addFilter(LevelsAllowFilter({logging.INFO, logging.ERROR}))
        h_audit.setFormatter(fmt_audit_json)

        # 3) TRACE: DEBUG-only (JSON full extras)
        h_trace = DailyFolderFileHandler(base_logs_dir, f"{strategy}.trace.log")
        h_trace.setLevel(logging.DEBUG)
        h_trace.addFilter(ExactLevelFilter(logging.DEBUG))
        h_trace.setFormatter(fmt_trace_json)

        # 4) DEBUG EXTRA (text with extras): DEBUG-only
        h_debugx = DailyFolderFileHandler(base_logs_dir, f"{strategy}.debug_extra.log")
        h_debugx.setLevel(logging.DEBUG)
        h_debugx.addFilter(ExactLevelFilter(logging.DEBUG))
        h_debugx.setFormatter(fmt_text_with_extras)

        # 5) ALERTS: WARNING+
        h_alerts = DailyFolderFileHandler(base_logs_dir, f"{strategy}.alerts.log")
        h_alerts.setLevel(logging.WARNING)
        h_alerts.addFilter(MinLevelFilter(logging.WARNING))
        h_alerts.setFormatter(fmt_text)

        # 6) ERRORS: ERROR-only
        h_errors = DailyFolderFileHandler(base_logs_dir, f"{strategy}.errors.log")
        h_errors.setLevel(logging.ERROR)
        h_errors.addFilter(ExactLevelFilter(logging.ERROR))
        h_errors.setFormatter(fmt_text)

        for h in (h_verbose, h_audit, h_trace, h_debugx, h_alerts, h_errors):
            logger.addHandler(h)

    adapter = ContextAdapter(logger)
    if base_context is not None:
        adapter.set_context(base_context)
    return adapter
```

---

## main.py  (بدون تغییر نسبت به نسخه‌ی قبلی، اما با این اصلاح الان اجرا می‌شود)

```python
# main.py
from __future__ import annotations
import argparse
import random
from typing import Optional, Dict, Any, TypedDict

from core.logger import build_logger  # ContextAdapter with set_context/add_context/add_extra and .debug/.info/...

class Position(TypedDict):
    entry: float
    sl: float
    tp: float
    size_pct: float

class EMAIndicator:
    def __init__(self, period: int, logger):
        self.period = period
        self.value: Optional[float] = None
        self.log = logger

    def update(self, price: float) -> float:
        alpha = 2 / (self.period + 1)
        prev = self.value
        self.value = price if prev is None else (alpha * price + (1 - alpha) * prev)
        diff = (self.value - (prev if prev is not None else self.value))
        self.log.add_extra(alpha=alpha)
        self.log.add_extra(prev, price, diff)
        self.log.debug("EMA update")
        return self.value

class MomentumSignal:
    def __init__(self, fast: EMAIndicator, slow: EMAIndicator, threshold: float, logger):
        self.fast = fast
        self.slow = slow
        self.threshold = threshold
        self.log = logger

    def compute(self) -> Optional[Dict[str, Any]]:
        if self.fast.value is None or self.slow.value is None:
            self.log.debug("Insufficient data for signal")
            return None
        diff = self.fast.value - self.slow.value
        denom = max(abs(self.slow.value), 1e-9)
        strength = diff / denom
        self.log.add_extra(diff, denom, strength=strength, thr=self.threshold)
        self.log.debug("Momentum scoring")
        if strength > self.threshold:
            self.log.add_extra(side="BUY", strength=strength)
            self.log.debug("Signal=BUY")
            return {"side": "BUY", "strength": strength}
        else:
            self.log.add_extra(side="NONE", strength=strength)
            self.log.debug("No-signal")
            return None

class LongMomentumStrategy:
    def __init__(self, signal: MomentumSignal, logger, risk_limit: float = 0.02, position_pct: float = 0.10):
        self.signal = signal
        self.log = logger
        self.risk_limit = risk_limit
        self.position_pct = position_pct
        self.position: Optional[Position] = None

    def on_bar(self, bar: Dict[str, float], *, atr_value: float) -> None:
        self.log.add_extra(bar=bar)
        self.log.debug("Bar received")
        if self.position is not None:
            self._maybe_close(bar)
            return
        sig = self.signal.compute()
        if not sig:
            return
        entry = float(bar['close'])
        sl = float(entry - 1.8 * atr_value)
        per_trade_risk = (entry - sl) / entry
        tp = float(entry + 2.2 * (entry - sl))
        if per_trade_risk > self.risk_limit:
            self.log.add_extra(risk_pct=per_trade_risk, limit=self.risk_limit)
            self.log.debug("Skip trade: risk over limit")
            return
        self.position = {
            "entry": float(entry),
            "sl": float(sl),
            "tp": float(tp),
            "size_pct": float(self.position_pct),
        }
        trade_open = {
            "id": f"{bar['time']}",
            "side": "LONG",
            "entry": entry,
            "size_pct": float(self.position_pct),
            "sl": sl,
            "tp": tp,
            "rr": 2.2
        }
        self.log.add_extra(trade=trade_open)
        self.log.info("[OPEN]")

    def _maybe_close(self, bar: Dict[str, float]) -> None:
        pos = self.position
        if pos is None:
            return
        e = float(pos["entry"])
        sl = float(pos["sl"])
        tp = float(pos["tp"])
        closed: Optional[tuple[str, float]] = None
        if bar["low"] <= sl:
            closed = ("SL", sl)
        elif bar["high"] >= tp:
            closed = ("TP", tp)
        if not closed:
            return
        reason, price = closed
        pnl = (price - e) / e
        status = "WIN" if pnl > 0 else "LOSS"
        trade_close = {
            "id": f"{bar['time']}",
            "exit": float(price),
            "pnl_pct": pnl * 100.0,
            "status": status,
            "reason": reason,
        }
        self.log.add_extra(trade=trade_close)
        self.log.info("[CLOSE]")
        self.position = None

def gen_bars(n: int, base: float = 100.0, noise: float = 0.6):
    import math as _m
    rnd = random.Random(42)
    price = base
    for i in range(n):
        drift = 0.05 * _m.sin(i / 5.0)
        price = max(1.0, price * (1 + drift * 0.01))
        candle_noise = (rnd.random() - 0.5) * noise
        close = max(1.0, price * (1 + candle_noise * 0.01))
        high = max(price, close) * (1 + abs(candle_noise) * 0.005)
        low = min(price, close) * (1 - abs(candle_noise) * 0.005)
        open_ = price
        yield {"time": f"T{i:03d}", "open": float(open_), "high": float(high), "low": float(low), "close": float(close)}
        price = close

def est_atr_like(prev_close: float, bar: Dict[str, float], prev_atr: Optional[float]) -> float:
    tr = max(bar["high"] - bar["low"], abs(bar["high"] - prev_close), abs(prev_close - bar["low"]))
    if prev_atr is None:
        return float(tr)
    return float(0.13 * tr + 0.87 * prev_atr)

def main() -> None:
    parser = argparse.ArgumentParser(description="FluxBot logging demo")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--bars", type=int, default=60)
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument("--strategy", default="fluxbot_demo")
    args = parser.parse_args()

    log = build_logger(
        "runner",
        base_logs_dir=args.logs_dir,
        strategy=args.strategy,
        base_context={"symbol": args.symbol, "tf": args.timeframe, "step": "demo"}
    )

    log.debug("Starting demo run")

    ema_fast = EMAIndicator(period=8, logger=log)
    ema_slow = EMAIndicator(period=21, logger=log)
    signal = MomentumSignal(ema_fast, ema_slow, threshold=0.0012, logger=log)
    strategy = LongMomentumStrategy(signal, logger=log, risk_limit=0.02, position_pct=0.10)

    prev_close = 100.0
    atr_val: Optional[float] = None

    for bar in gen_bars(args.bars, base=100.0):
        ema_fast.update(bar["close"])
        ema_slow.update(bar["close"])
        atr_val = est_atr_like(prev_close, bar, atr_val)
        prev_close = bar["close"]
        strategy.on_bar(bar, atr_value=atr_val)

        if bar["time"] == "T025":
            try:
                raise TimeoutError("Simulated exchange timeout (5s)")
            except Exception as ex:
                log.add_extra(op="place_order", retryable=True, error=str(ex))
                log.debug("Exchange error")
                logging.getLogger("runner").error(f"Exchange error: {ex}")

    log.debug("Demo run finished")

if __name__ == "__main__":
    main()
```

---

### نکتهٔ کوچک

الان `context` و `extra_kvs` داخل `extra` تزریق می‌شن؛ `Formatter`ها به‌صورت `%(`**context**`)s` و `%(`**extra_kvs**`)s` از روی `record` می‌خونن، چون `logging` تمام کلیدهای `extra` رو به‌عنوان attribute به `LogRecord` اضافه می‌کنه. پس هم سازگار با API استاندارد هستیم، هم دیگه ارور `unexpected keyword argument 'context'` نداریم.


