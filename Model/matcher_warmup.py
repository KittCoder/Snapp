from __future__ import annotations

import os
import platform
import sys
import threading
import time
from dataclasses import asdict, dataclass, fields
from logging import ERROR
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
    semantic_readiness: str = "unavailable"

    def safe_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("error", None)
        if self.error:
            payload["error"] = "warmup failed"
        return payload


_state = WarmupState()
_lock = threading.Lock()
_thread: threading.Thread | None = None


def _matching_module_keys() -> list[str]:
    return sorted(key for key in sys.modules if key == "matcher_warmup" or key.endswith(".matcher_warmup"))


def _duplicate_module_keys() -> list[str]:
    current_file = os.path.realpath(__file__)
    duplicates = []
    for key in _matching_module_keys():
        module = sys.modules.get(key)
        module_file = getattr(module, "__file__", None)
        if module_file and os.path.realpath(module_file) == current_file and key != __name__:
            duplicates.append(key)
    return sorted(duplicates)


def _runtime_context() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        "python": platform.python_version(),
        "warmup_thread_alive": bool(_thread and _thread.is_alive()),
        "warmup_module_name": __name__,
        "warmup_module_file": __file__,
        "warmup_module_keys": _matching_module_keys(),
        "warmup_duplicate_module_keys": _duplicate_module_keys(),
        "warmup_manager_id": id(sys.modules[__name__]),
        "warmup_state_id": id(_state),
    }


def module_diagnostics(include_private_ids: bool = False) -> dict[str, Any]:
    diagnostics = {
        "module_name": __name__,
        "module_keys": _matching_module_keys(),
        "duplicate_module_keys": _duplicate_module_keys(),
    }
    if include_private_ids:
        diagnostics.update(
            {
                "module_file": __file__,
                "manager_id": id(sys.modules[__name__]),
                "state_id": id(_state),
                "pid": os.getpid(),
                "thread": threading.current_thread().name,
            }
        )
    return diagnostics


def _log_duplicate_modules_if_present() -> None:
    duplicates = _duplicate_module_keys()
    if duplicates:
        log_event("matcher_warmup_duplicate_module_detected", level=ERROR, **_runtime_context())


def _log_warmup_return(reason: str, state: WarmupState) -> None:
    log_event(
        "matcher_warmup_return",
        reason=reason,
        status=state.status,
        warmup_completed=state.warmup_completed,
        artifact_validation_ok=state.artifact_validation_ok,
        **_runtime_context(),
    )


def _state_snapshot_locked() -> WarmupState:
    return WarmupState(**asdict(_state))


def _replace_state_locked(new_state: WarmupState) -> None:
    for field in fields(WarmupState):
        setattr(_state, field.name, getattr(new_state, field.name))


def _set_state_fields_locked(**updates: Any) -> None:
    for key, value in updates.items():
        setattr(_state, key, value)


def warmup_status() -> WarmupState:
    with _lock:
        return _state_snapshot_locked()


def warmup_matcher(force: bool = False) -> WarmupState:
    _log_duplicate_modules_if_present()
    with _lock:
        if _state.warmup_completed and not force:
            snapshot = _state_snapshot_locked()
            _log_warmup_return("already_completed", snapshot)
            return snapshot
        if _state.status == "warming" and not force:
            snapshot = _state_snapshot_locked()
            _log_warmup_return("already_warming", snapshot)
            return snapshot
        _replace_state_locked(WarmupState(status="warming", started_at=time.time()))

    log_event("matcher_warmup_start", **_runtime_context())

    started = time.perf_counter()
    try:
        validation = validate_runtime_artifacts()
        with _lock:
            _set_state_fields_locked(
                artifact_validation_ok=validation.ok,
                artifact_validation_status=validation.status,
            )
        if not validation.ok:
            raise RuntimeError("; ".join(validation.errors))
        service = get_product_match_service()
        retriever = service.retriever
        _ = service.overrides.version
        _ = retriever.features
        with _lock:
            _state.features_loaded = True
        _ = retriever.eligible_features
        _ = retriever.lexical_indexes()
        _ = retriever.lexical_docs
        with _lock:
            _state.lexical_index_loaded = True
        index_loaded = retriever.load_index()
        with _lock:
            _state.index_loaded = index_loaded
        if not index_loaded and os.getenv("SNAPP_ALLOW_LEXICAL_ONLY", "").lower() not in {"1", "true", "yes"}:
            raise RuntimeError("matcher vector index is unavailable")
        retriever.backend.load()
        model_loaded = getattr(retriever.backend, "load_error", None) is None
        with _lock:
            _state.model_loaded = model_loaded
        if not model_loaded and os.getenv("SNAPP_ALLOW_LEXICAL_ONLY", "").lower() not in {"1", "true", "yes"}:
            raise RuntimeError("embedding model is unavailable")
        service.match_recipe_ingredients(WARMUP_QUERIES)
        get_basket_builder()
        with _lock:
            _state.status = "ready" if _state.index_loaded and _state.model_loaded else "degraded"
            _state.semantic_readiness = "ready" if _state.status == "ready" else "lexical_only"
            _state.warmup_completed = True
            _state.finished_at = time.time()
            _state.startup_ms = round((time.perf_counter() - started) * 1000, 2)
            metrics.set_startup_readiness(_state.startup_ms)
            metrics.set_artifact_version((validation.manifest or {}).get("index_hash"))
            log_event("matcher_warmup_complete", status=_state.status, startup_ms=_state.startup_ms)
            snapshot = _state_snapshot_locked()
            _log_warmup_return("completed", snapshot)
            return snapshot
    except Exception as exc:
        with _lock:
            _state.status = "failed"
            _state.semantic_readiness = "unavailable"
            _state.error = str(exc)
            _state.finished_at = time.time()
            _state.startup_ms = round((time.perf_counter() - started) * 1000, 2)
            metrics.increment("startup_failures")
            log_event("matcher_warmup_failed", status=_state.status, startup_ms=_state.startup_ms, error_type=type(exc).__name__)
            snapshot = _state_snapshot_locked()
            _log_warmup_return("failed", snapshot)
            return snapshot


def start_background_warmup() -> WarmupState:
    global _thread
    _log_duplicate_modules_if_present()
    with _lock:
        if _state.status in {"warming", "ready", "degraded"}:
            snapshot = _state_snapshot_locked()
            log_event("matcher_background_warmup_return", reason="already_started", status=snapshot.status, **_runtime_context())
            return snapshot
        _replace_state_locked(WarmupState(status="warming", started_at=time.time()))
        _thread = threading.Thread(target=lambda: warmup_matcher(force=True), name="snapp-matcher-warmup", daemon=True)
        _thread.start()
        snapshot = _state_snapshot_locked()
        log_event("matcher_background_warmup_return", reason="thread_started", status=snapshot.status, **_runtime_context())
        return snapshot


log_event("matcher_warmup_module_imported", **_runtime_context())
