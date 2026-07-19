from __future__ import annotations

import os
import sys
import threading
import time
import traceback
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


def _caller_location() -> str:
    stack = traceback.extract_stack(limit=6)
    for frame in reversed(stack[:-1]):
        if frame.filename != __file__:
            return f"{os.path.basename(frame.filename)}:{frame.lineno}:{frame.name}"
    frame = stack[-2]
    return f"{os.path.basename(frame.filename)}:{frame.lineno}:{frame.name}"


def _format_diag(event_name: str, fields: dict[str, Any]) -> str:
    keys = (
        "pid",
        "ppid",
        "thread",
        "warmup_module_name",
        "warmup_manager_id",
        "warmup_state_id",
        "status",
        "warmup_completed",
        "model_loaded",
        "index_loaded",
        "finished_at",
        "reason",
        "warmup_duplicate_module_keys",
    )
    pieces = [event_name]
    for key in keys:
        if key in fields:
            pieces.append(f"{key}={fields[key]}")
    return " ".join(pieces)


class WarmupManager:
    def __init__(self) -> None:
        self._state = WarmupState()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        fields = {
            "manager_id": id(self),
            "state_id": id(self._state),
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "thread": threading.current_thread().name,
            "caller": _caller_location(),
            "creation_stack": "".join(traceback.format_stack(limit=8)),
            "module_name": __name__,
            "module_file": __file__,
            "module_keys": _matching_module_keys(),
            "duplicate_module_keys": _duplicate_module_keys(),
            "warmup_module_name": __name__,
            "warmup_manager_id": id(self),
            "warmup_state_id": id(self._state),
            "status": self._state.status,
            "warmup_completed": self._state.warmup_completed,
            "model_loaded": self._state.model_loaded,
            "index_loaded": self._state.index_loaded,
            "finished_at": self._state.finished_at,
        }
        log_event(_format_diag("matcher_warmup_manager_created", fields), event_name="matcher_warmup_manager_created", **fields)

    def _runtime_context(self) -> dict[str, Any]:
        return {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "thread": threading.current_thread().name,
            "warmup_thread_alive": bool(self._thread and self._thread.is_alive()),
            "warmup_module_name": __name__,
            "warmup_module_file": __file__,
            "warmup_module_keys": _matching_module_keys(),
            "warmup_duplicate_module_keys": _duplicate_module_keys(),
            "warmup_manager_id": id(self),
            "warmup_state_id": id(self._state),
            "status": self._state.status,
            "warmup_completed": self._state.warmup_completed,
            "model_loaded": self._state.model_loaded,
            "index_loaded": self._state.index_loaded,
            "finished_at": self._state.finished_at,
        }

    def diagnostics(self, include_private_ids: bool = False) -> dict[str, Any]:
        with self._lock:
            diagnostics = {
                "module_name": __name__,
                "module_keys": _matching_module_keys(),
                "duplicate_module_keys": _duplicate_module_keys(),
                "warmup_state_status": self._state.status,
                "warmup_state_completed": self._state.warmup_completed,
                "warmup_state_model_loaded": self._state.model_loaded,
                "warmup_state_index_loaded": self._state.index_loaded,
                "warmup_state_finished_at": self._state.finished_at,
            }
            if include_private_ids:
                diagnostics.update(
                    {
                        "module_file": __file__,
                        "manager_id": id(self),
                        "state_id": id(self._state),
                        "pid": os.getpid(),
                        "thread": threading.current_thread().name,
                    }
                )
            return diagnostics

    def _log_duplicate_modules_if_present(self) -> None:
        duplicates = _duplicate_module_keys()
        if duplicates:
            fields = self._runtime_context()
            log_event(_format_diag("matcher_warmup_duplicate_module_detected", fields), level=ERROR, event_name="matcher_warmup_duplicate_module_detected", **fields)

    def _snapshot_locked(self) -> WarmupState:
        return WarmupState(**asdict(self._state))

    def _copy_fields_locked(self, new_state: WarmupState) -> None:
        for field in fields(WarmupState):
            setattr(self._state, field.name, getattr(new_state, field.name))

    def _set_fields_locked(self, **updates: Any) -> None:
        for key, value in updates.items():
            setattr(self._state, key, value)

    def snapshot(self) -> WarmupState:
        with self._lock:
            return self._snapshot_locked()

    def _log_return(self, reason: str, state: WarmupState) -> None:
        fields = {"reason": reason, "artifact_validation_ok": state.artifact_validation_ok, **self._runtime_context()}
        log_event(_format_diag("matcher_warmup_return", fields), event_name="matcher_warmup_return", **fields)

    def _log_stage(self, event_name: str, **extra: Any) -> None:
        fields = {**extra, **self._runtime_context()}
        log_event(_format_diag(event_name, fields), event_name=event_name, **fields)

    def warmup(self, force: bool = False) -> WarmupState:
        self._log_duplicate_modules_if_present()
        with self._lock:
            if self._state.warmup_completed and not force:
                snapshot = self._snapshot_locked()
                self._log_return("already_completed", snapshot)
                return snapshot
            if self._state.status == "warming" and not force:
                snapshot = self._snapshot_locked()
                self._log_return("already_warming", snapshot)
                return snapshot
            self._copy_fields_locked(WarmupState(status="warming", started_at=time.time()))

        self._log_stage("matcher_warmup_start")
        started = time.perf_counter()
        try:
            validation = validate_runtime_artifacts()
            with self._lock:
                self._set_fields_locked(
                    artifact_validation_ok=validation.ok,
                    artifact_validation_status=validation.status,
                )
            self._log_stage("matcher_warmup_stage_artifact_validation", artifact_validation_ok=validation.ok, artifact_validation_status=validation.status)
            if not validation.ok:
                raise RuntimeError("; ".join(validation.errors))

            service = get_product_match_service()
            retriever = service.retriever
            _ = service.overrides.version
            _ = retriever.features
            with self._lock:
                self._state.features_loaded = True
            self._log_stage("matcher_warmup_stage_features_loaded")
            _ = retriever.eligible_features
            _ = retriever.lexical_indexes()
            _ = retriever.lexical_docs
            with self._lock:
                self._state.lexical_index_loaded = True
            self._log_stage("matcher_warmup_stage_lexical_loaded")

            index_loaded = retriever.load_index()
            with self._lock:
                self._state.index_loaded = index_loaded
            self._log_stage("matcher_warmup_stage_index_loaded")
            if not index_loaded and os.getenv("SNAPP_ALLOW_LEXICAL_ONLY", "").lower() not in {"1", "true", "yes"}:
                raise RuntimeError("matcher vector index is unavailable")

            retriever.backend.load()
            model_loaded = getattr(retriever.backend, "load_error", None) is None
            with self._lock:
                self._state.model_loaded = model_loaded
            self._log_stage("matcher_warmup_stage_model_loaded")
            if not model_loaded and os.getenv("SNAPP_ALLOW_LEXICAL_ONLY", "").lower() not in {"1", "true", "yes"}:
                raise RuntimeError("embedding model is unavailable")

            service.match_recipe_ingredients(WARMUP_QUERIES)
            get_basket_builder()
            self._log_stage("matcher_warmup_stage_probe_complete")
            with self._lock:
                self._state.status = "ready" if self._state.index_loaded and self._state.model_loaded else "degraded"
                self._state.semantic_readiness = "ready" if self._state.status == "ready" else "lexical_only"
                self._state.artifact_validation_ok = True
                self._state.artifact_validation_status = "ready"
                self._state.features_loaded = True
                self._state.index_loaded = index_loaded
                self._state.lexical_index_loaded = True
                self._state.model_loaded = model_loaded
                self._state.warmup_completed = True
                self._state.finished_at = time.time()
                self._state.startup_ms = round((time.perf_counter() - started) * 1000, 2)
                metrics.set_startup_readiness(self._state.startup_ms)
                metrics.set_artifact_version((validation.manifest or {}).get("index_hash"))
                snapshot = self._snapshot_locked()

            self._log_stage("matcher_warmup_complete", startup_ms=snapshot.startup_ms)
            self._log_return("completed", snapshot)
            return snapshot
        except Exception as exc:
            with self._lock:
                self._state.status = "failed"
                self._state.semantic_readiness = "unavailable"
                self._state.error = str(exc)
                self._state.finished_at = time.time()
                self._state.startup_ms = round((time.perf_counter() - started) * 1000, 2)
                metrics.increment("startup_failures")
                snapshot = self._snapshot_locked()
            fields = {"startup_ms": snapshot.startup_ms, "error_type": type(exc).__name__, **self._runtime_context()}
            log_event(_format_diag("matcher_warmup_failed", fields), event_name="matcher_warmup_failed", **fields)
            self._log_return("failed", snapshot)
            return snapshot

    def start_once(self) -> WarmupState:
        self._log_duplicate_modules_if_present()
        self._log_stage("matcher_background_warmup_invoked")
        with self._lock:
            if self._state.status in {"warming", "ready", "degraded"}:
                snapshot = self._snapshot_locked()
                fields = {"reason": "already_started", **self._runtime_context()}
                log_event(_format_diag("matcher_background_warmup_return", fields), event_name="matcher_background_warmup_return", **fields)
                return snapshot
            self._copy_fields_locked(WarmupState(status="warming", started_at=time.time()))
            self._thread = threading.Thread(target=lambda: self.warmup(force=True), name="snapp-matcher-warmup", daemon=True)
            self._thread.start()
            snapshot = self._snapshot_locked()
        fields = {"reason": "thread_started", **self._runtime_context()}
        log_event(_format_diag("matcher_background_warmup_return", fields), event_name="matcher_background_warmup_return", **fields)
        return snapshot

    def reset_for_tests(self) -> None:
        with self._lock:
            self._copy_fields_locked(WarmupState())
            self._thread = None


_MANAGER = WarmupManager()


def get_warmup_status() -> WarmupState:
    return _MANAGER.snapshot()


def warmup_status() -> WarmupState:
    return get_warmup_status()


def warmup_matcher(force: bool = False) -> WarmupState:
    return _MANAGER.warmup(force=force)


def start_background_warmup() -> WarmupState:
    return _MANAGER.start_once()


def module_diagnostics(include_private_ids: bool = False) -> dict[str, Any]:
    return _MANAGER.diagnostics(include_private_ids=include_private_ids)


def reset_for_tests() -> None:
    _MANAGER.reset_for_tests()


_module_import_fields = _MANAGER._runtime_context()
log_event(_format_diag("matcher_warmup_module_imported", _module_import_fields), event_name="matcher_warmup_module_imported", **_module_import_fields)
