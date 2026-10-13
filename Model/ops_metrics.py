from __future__ import annotations

import json
import logging
import os
import resource
import threading
import time
import uuid
from collections import Counter
from typing import Any


LOGGER_NAME = "snapp"
LOG_JSON = os.getenv("SNAPP_LOG_FORMAT", "").casefold() == "json" or os.getenv("SNAPP_ENV", "").casefold() == "production"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "structured", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if LOG_JSON else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(os.getenv("SNAPP_LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    return logger


logger = configure_logging()


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    import re
    def sanitize(value):
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()
                    if not re.search(r"password|token|authorization|api.?key|secret|cookie", str(key), re.I)}
        if isinstance(value, (list, tuple)):
            return [sanitize(item) for item in value[:50]]
        if isinstance(value, str):
            value = re.sub(r"Bearer\s+\S+", "[redacted]", value, flags=re.I)
            value = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", "[redacted]", value)
            return value.replace("\n", " ").replace("\r", " ")[:500]
        return value
    safe_fields = sanitize(fields)
    logger.log(level, sanitize(event), extra={"structured": {"event": sanitize(event), **safe_fields}})


def request_id() -> str:
    return uuid.uuid4().hex[:16]


class OpsMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters = Counter()
        self.latency_buckets = Counter()
        self.started_at = time.time()
        self.startup_readiness_ms: float | None = None
        self.active_artifact_version: str | None = None

    def increment(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[key] += amount

    def observe_latency(self, key: str, milliseconds: float) -> None:
        if milliseconds < 100:
            bucket = "lt_100ms"
        elif milliseconds < 500:
            bucket = "lt_500ms"
        elif milliseconds < 1000:
            bucket = "lt_1s"
        elif milliseconds < 3000:
            bucket = "lt_3s"
        else:
            bucket = "gte_3s"
        with self._lock:
            self.latency_buckets[f"{key}:{bucket}"] += 1

    def set_startup_readiness(self, milliseconds: float | None) -> None:
        with self._lock:
            self.startup_readiness_ms = milliseconds

    def set_artifact_version(self, version: str | None) -> None:
        with self._lock:
            self.active_artifact_version = version

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self.counters)
            latency = dict(self.latency_buckets)
            startup_ms = self.startup_readiness_ms
            artifact = self.active_artifact_version
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "uptime_seconds": round(time.time() - self.started_at, 2),
            "counters": counters,
            "latency_buckets": latency,
            "startup_readiness_ms": startup_ms,
            "active_artifact_version": artifact,
            "memory": {"max_rss_kb": rss_kb},
        }

    def reset(self) -> None:
        with self._lock:
            self.counters.clear()
            self.latency_buckets.clear()


metrics = OpsMetrics()
