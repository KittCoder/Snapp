from __future__ import annotations

import os
import platform
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from basket_quantity import get_basket_builder
from artifact_manifest import validate_runtime_artifacts
from ops_metrics import log_event, metrics
from product_compatibility import get_product_match_service


WARMUP_QUERIES = ["milk", "chicken broth", "olive oil", "all-purpose flour"]


@dataclass
class WarmupState:
    status: str = "not_started"
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    model_loaded: bool = False
    index_loaded: bool = False
    features_loaded: bool = False
    lexical_index_loaded: bool = False
    warmup_completed: bool = False
    startup_ms: float | None = None
    artifact_validation_ok: bool = False
    artifact_validation_status: str | None = None

    def safe_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("error", None)
        if self.error:
            payload["error"] = "warmup failed"
        return payload


_state = WarmupState()
_lock = threading.Lock()
_thread: threading.Thread | None = None


def _runtime_context() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        "python": platform.python_version(),
        "warmup_thread_alive": bool(_thread and _thread.is_alive()),
    }


def _log_warmup_return(reason: str, state: WarmupState) -> None:
    log_event(
        "matcher_warmup_return",
        reason=reason,
        status=state.status,
        warmup_completed=state.warmup_completed,
        artifact_validation_ok=state.artifact_validation_ok,
        **_runtime_context(),
    )


def warmup_status() -> WarmupState:
    return _state


def warmup_matcher(force: bool = False) -> WarmupState:
    global _state
    with _lock:
        if _state.warmup_completed and not force:
            _log_warmup_return("already_completed", _state)
            return _state
        if _state.status == "warming" and not force:
            _log_warmup_return("already_warming", _state)
            return _state
        _state = WarmupState(status="warming", started_at=time.time())

    started = time.perf_counter()
    try:
        validation = validate_runtime_artifacts()
        _state.artifact_validation_ok = validation.ok
        _state.artifact_validation_status = validation.status
        if not validation.ok:
            raise RuntimeError("; ".join(validation.errors))
        service = get_product_match_service()
        retriever = service.retriever
        _ = service.overrides.version
        _ = retriever.features
        _state.features_loaded = True
        _ = retriever.eligible_features
        _ = retriever.lexical_indexes()
        _ = retriever.lexical_docs
        _state.lexical_index_loaded = True
        _state.index_loaded = retriever.load_index()
        if not _state.index_loaded and os.getenv("SNAPP_ALLOW_LEXICAL_ONLY", "").lower() not in {"1", "true", "yes"}:
            raise RuntimeError("matcher vector index is unavailable")
        retriever.backend.load()
        _state.model_loaded = getattr(retriever.backend, "load_error", None) is None
        if not _state.model_loaded and os.getenv("SNAPP_ALLOW_LEXICAL_ONLY", "").lower() not in {"1", "true", "yes"}:
            raise RuntimeError("embedding model is unavailable")
        service.match_recipe_ingredients(WARMUP_QUERIES)
        get_basket_builder()
        with _lock:
            _state.status = "ready" if _state.index_loaded and _state.model_loaded else "degraded"
            _state.warmup_completed = True
            _state.finished_at = time.time()
            _state.startup_ms = round((time.perf_counter() - started) * 1000, 2)
            metrics.set_startup_readiness(_state.startup_ms)
            metrics.set_artifact_version((validation.manifest or {}).get("index_hash"))
            log_event("matcher_warmup_complete", status=_state.status, startup_ms=_state.startup_ms)
            _log_warmup_return("completed", _state)
    except Exception as exc:
        with _lock:
            _state.status = "failed"
            _state.error = str(exc)
            _state.finished_at = time.time()
            _state.startup_ms = round((time.perf_counter() - started) * 1000, 2)
            metrics.increment("startup_failures")
            log_event("matcher_warmup_failed", status=_state.status, startup_ms=_state.startup_ms, error_type=type(exc).__name__)
            _log_warmup_return("failed", _state)
    return _state


def start_background_warmup() -> WarmupState:
    global _thread
    with _lock:
        if _state.status in {"warming", "ready", "degraded"}:
            log_event("matcher_background_warmup_return", reason="already_started", status=_state.status, **_runtime_context())
            return _state
        _thread = threading.Thread(target=warmup_matcher, name="snapp-matcher-warmup", daemon=True)
        _thread.start()
        log_event("matcher_background_warmup_return", reason="thread_started", status=_state.status, **_runtime_context())
        return _state
