from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from basket_quantity import get_basket_builder
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

    def safe_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("error", None)
        if self.error:
            payload["error"] = "warmup failed"
        return payload


_state = WarmupState()
_lock = threading.Lock()
_thread: threading.Thread | None = None


def warmup_status() -> WarmupState:
    return _state


def warmup_matcher(force: bool = False) -> WarmupState:
    global _state
    with _lock:
        if _state.warmup_completed and not force:
            return _state
        if _state.status == "warming" and not force:
            return _state
        _state = WarmupState(status="warming", started_at=time.time())

    started = time.perf_counter()
    try:
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
    except Exception as exc:
        with _lock:
            _state.status = "failed"
            _state.error = str(exc)
            _state.finished_at = time.time()
            _state.startup_ms = round((time.perf_counter() - started) * 1000, 2)
    return _state


def start_background_warmup() -> WarmupState:
    global _thread
    with _lock:
        if _state.status in {"warming", "ready", "degraded"}:
            return _state
        _thread = threading.Thread(target=warmup_matcher, name="snapp-matcher-warmup", daemon=True)
        _thread.start()
        return _state

