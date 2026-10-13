from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from ingredient_normalization import (
    ALIAS_TO_CANONICAL,
    PROBABLE_PRODUCT,
    VALID_PRODUCT,
    apply_alias,
    canonical_for_product,
    infer_category,
    normalize_text,
    parse_ingredient,
)


MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_FEATURES_PATH = MODEL_DIR / "morton_williams_product_features.json"
DEFAULT_INDEX_DIR = MODEL_DIR / "morton_williams_vector_index"
DEFAULT_MODEL_NAME = os.getenv("SNAPP_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
INDEX_VERSION = "product-candidate-index-v1"
EMBEDDINGS_FILENAME = "embeddings.npy"
METADATA_FILENAME = "metadata.json"


@dataclass
class Candidate:
    product_id: str
    original_product_name: str
    normalized_name: str
    record_status: str
    canonical_ingredient: str | None
    lexical_similarity: float = 0.0
    semantic_similarity: float | None = None
    exact_match: bool = False
    alias_match: bool = False
    category_match_signal: str = "unknown"
    retrieval_reason_codes: list[str] = field(default_factory=list)
    source_rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateRetrievalResult:
    ingredient_text: str
    parsed_query: dict[str, Any]
    normalized_semantic_query: str
    candidates: list[Candidate]
    retrieval_latency_ms: float
    lexical_latency_ms: float
    semantic_latency_ms: float | None
    query_embedding_latency_ms: float | None
    embedding_index_available: bool
    embedding_model_version: str | None
    index_version: str | None
    degraded_mode: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return payload


def stable_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def token_variants(token: str) -> set[str]:
    variants = {token}
    if token.endswith("ies") and len(token) > 3:
        variants.add(f"{token[:-3]}y")
    if token.endswith("es") and len(token) > 2:
        variants.add(token[:-2])
    if token.endswith("s") and len(token) > 1:
        variants.add(token[:-1])
    else:
        variants.add(f"{token}s")
        variants.add(f"{token}es")
    return variants


def eligible_product(feature: dict[str, Any]) -> bool:
    return (
        feature.get("eligible_for_retrieval") is True
        and feature.get("record_status") in {VALID_PRODUCT, PROBABLE_PRODUCT}
        and bool(feature.get("normalized_name"))
    )


def product_embedding_text(feature: dict[str, Any]) -> str:
    parts = [
        feature.get("normalized_name"),
        feature.get("canonical_name"),
        feature.get("category"),
        feature.get("form"),
        feature.get("fat_level"),
        feature.get("salted_status"),
        feature.get("sweetened_status"),
        feature.get("freshness"),
        feature.get("bone_status"),
        feature.get("skin_status"),
        " ".join(feature.get("dietary_attributes") or []),
        feature.get("brand"),
    ]
    return " | ".join(str(part).strip() for part in parts if part)


def query_embedding_text(ingredient_text: str) -> tuple[str, dict[str, Any]]:
    parsed = parse_ingredient(ingredient_text)
    recognized = canonical_for_product(parsed.canonical_name)
    parts = [
        parsed.fat_level,
        parsed.salted_status,
        parsed.sweetened_status,
        parsed.freshness,
        parsed.form,
        parsed.bone_status,
        parsed.skin_status,
        " ".join(parsed.dietary_qualifiers),
        parsed.canonical_name,
        recognized if recognized != parsed.canonical_name else None,
    ]
    text = normalize_text(" ".join(part for part in parts if part))
    return apply_alias(text), parsed.to_dict()


class SentenceTransformerEmbeddingBackend:
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._load_error = None
        self._load_started_at = None
        self._load_finished_at = None

    @property
    def model_version(self) -> str:
        return self.model_name

    @property
    def load_error(self) -> str | None:
        return self._load_error

    @property
    def model_load_ms(self) -> float | None:
        if self._load_started_at is None or self._load_finished_at is None:
            return None
        return round((self._load_finished_at - self._load_started_at) * 1000, 2)

    def load(self):
        if self._model is not None or self._load_error:
            return self._model
        self._load_started_at = time.perf_counter()
        try:
            from sentence_transformers import SentenceTransformer

            # Server workers use CPU: macOS Metal initialization is unsafe after
            # Gunicorn forks with the security-updated PyTorch runtime.
            self._model = SentenceTransformer(
                self.model_name, device=os.getenv("SNAPP_EMBEDDING_DEVICE", "cpu")
            )
        except Exception as exc:
            self._load_error = str(exc)
            self._model = None
        self._load_finished_at = time.perf_counter()
        return self._model

    def embed(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        model = self.load()
        if model is None:
            raise RuntimeError(f"Embedding model unavailable: {self._load_error}")
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return normalize_vectors(np.asarray(vectors, dtype=np.float32))


class DeterministicEmbeddingBackend:
    def __init__(self, dimension: int = 32, model_name: str = "deterministic-test-embedding"):
        self.dimension = dimension
        self.model_name = model_name
        self.load_count = 0

    @property
    def model_version(self) -> str:
        return self.model_name

    def load(self):
        self.load_count += 1
        return self

    def embed(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        self.load()
        vectors = []
        for text in texts:
            vector = np.zeros(self.dimension, dtype=np.float32)
            for token in normalize_text(text).split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = digest[0] % self.dimension
                vector[index] += 1.0
            vectors.append(vector)
        return normalize_vectors(np.vstack(vectors))


_embedding_backend_singleton: SentenceTransformerEmbeddingBackend | None = None


def embedding_backend() -> SentenceTransformerEmbeddingBackend:
    global _embedding_backend_singleton
    if _embedding_backend_singleton is None:
        _embedding_backend_singleton = SentenceTransformerEmbeddingBackend(DEFAULT_MODEL_NAME)
    return _embedding_backend_singleton


def load_features(path: Path = DEFAULT_FEATURES_PATH) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as file:
        payload = json.load(file)
    return payload.get("features") or []


def atomic_write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")
        temp_name = file.name
    os.replace(temp_name, path)


def load_existing_index(index_dir: Path) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    metadata_path = index_dir / METADATA_FILENAME
    embeddings_path = index_dir / EMBEDDINGS_FILENAME
    if not metadata_path.exists() or not embeddings_path.exists():
        return None, None
    with metadata_path.open(encoding="utf-8") as file:
        metadata = json.load(file)
    embeddings = np.load(embeddings_path)
    return embeddings, metadata


def build_product_index(
    features_path: Path = DEFAULT_FEATURES_PATH,
    index_dir: Path = DEFAULT_INDEX_DIR,
    backend: Any | None = None,
    batch_size: int = 64,
    failed_log_path: Path | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    backend = backend or embedding_backend()
    features = [feature for feature in load_features(features_path) if eligible_product(feature)]
    old_embeddings, old_metadata = load_existing_index(index_dir)
    old_by_id = {}
    if old_metadata and old_metadata.get("model_version") == backend.model_version:
        for row_index, row in enumerate(old_metadata.get("rows") or []):
            if old_embeddings is not None and row_index < len(old_embeddings):
                old_by_id[row.get("product_id")] = (row, old_embeddings[row_index])

    rows = []
    embeddings: list[np.ndarray | None] = []
    texts_to_embed = []
    positions_to_embed = []
    failed_rows = []
    skipped_unchanged = 0

    for source_rank, feature in enumerate(features):
        text = product_embedding_text(feature)
        text_hash = stable_text_hash(text)
        previous = old_by_id.get(feature.get("product_id"))
        row = {
            "product_id": feature.get("product_id"),
            "original_product_name": feature.get("original_product_name") or feature.get("normalized_name"),
            "normalized_name": feature.get("normalized_name"),
            "record_status": feature.get("record_status"),
            "canonical_name": feature.get("canonical_name"),
            "category": feature.get("category"),
            "subcategory": feature.get("subcategory"),
            "form": feature.get("form"),
            "fat_level": feature.get("fat_level"),
            "salted_status": feature.get("salted_status"),
            "freshness": feature.get("freshness"),
            "brand": feature.get("brand"),
            "dietary_attributes": feature.get("dietary_attributes") or [],
            "embedding_source_text": text,
            "embedding_source_hash": text_hash,
            "source_rank": source_rank,
        }
        rows.append(row)
        if previous and previous[0].get("embedding_source_hash") == text_hash:
            embeddings.append(np.asarray(previous[1], dtype=np.float32))
            skipped_unchanged += 1
        else:
            embeddings.append(None)
            texts_to_embed.append(text)
            positions_to_embed.append(len(rows) - 1)

    for offset in range(0, len(texts_to_embed), batch_size):
        batch_texts = texts_to_embed[offset : offset + batch_size]
        batch_positions = positions_to_embed[offset : offset + batch_size]
        try:
            batch_vectors = backend.embed(batch_texts, batch_size=batch_size)
        except Exception as exc:
            for position, text in zip(batch_positions, batch_texts):
                failed_rows.append(
                    {
                        "product_id": rows[position]["product_id"],
                        "normalized_name": rows[position]["normalized_name"],
                        "error": str(exc),
                    }
                )
            continue
        for position, vector in zip(batch_positions, batch_vectors):
            embeddings[position] = np.asarray(vector, dtype=np.float32)

    kept_rows = []
    kept_embeddings = []
    for row, vector in zip(rows, embeddings):
        if vector is None:
            continue
        kept_rows.append(row)
        kept_embeddings.append(vector)

    if kept_embeddings:
        matrix = normalize_vectors(np.vstack(kept_embeddings))
    else:
        matrix = np.zeros((0, 0), dtype=np.float32)

    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / EMBEDDINGS_FILENAME, matrix)
    metadata = {
        "index_version": INDEX_VERSION,
        "model_version": backend.model_version,
        "features_path": str(features_path),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "row_count": len(kept_rows),
        "embedding_dimension": int(matrix.shape[1]) if matrix.size else 0,
        "skipped_unchanged": skipped_unchanged,
        "rebuilt_vectors": len(texts_to_embed) - len(failed_rows),
        "failed_rows": len(failed_rows),
        "build_time_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "rows": kept_rows,
    }
    atomic_write_json(metadata, index_dir / METADATA_FILENAME)

    if failed_log_path:
        with Path(failed_log_path).open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["product_id", "normalized_name", "error"])
            writer.writeheader()
            writer.writerows(failed_rows)

    return metadata


class LruEmbeddingCache:
    def __init__(self, max_size: int = 256):
        self.max_size = max_size
        self._items: OrderedDict[tuple[str, str], np.ndarray] = OrderedDict()

    def get(self, key: tuple[str, str]) -> np.ndarray | None:
        value = self._items.get(key)
        if value is None:
            return None
        self._items.move_to_end(key)
        return value

    def set(self, key: tuple[str, str], value: np.ndarray) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()


@dataclass
class RetrievalStats:
    encode_calls: int = 0
    vector_searches: int = 0
    lexical_searches: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    embedding_ms: float = 0.0
    vector_ms: float = 0.0
    lexical_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProductCandidateRetriever:
    def __init__(
        self,
        features_path: Path = DEFAULT_FEATURES_PATH,
        index_dir: Path = DEFAULT_INDEX_DIR,
        backend: Any | None = None,
        cache_size: int = 2048,
        max_lexical_search_space: int = 350,
    ):
        self.features_path = Path(features_path)
        self.index_dir = Path(index_dir)
        self.backend = backend or embedding_backend()
        self.query_cache = LruEmbeddingCache(cache_size)
        self.max_lexical_search_space = max_lexical_search_space
        self._features: list[dict[str, Any]] | None = None
        self._eligible_features: list[dict[str, Any]] | None = None
        self._index_embeddings: np.ndarray | None = None
        self._index_metadata: dict[str, Any] | None = None
        self._index_error: str | None = None
        self._token_index: dict[str, set[int]] | None = None
        self._canonical_index: dict[str, set[int]] | None = None
        self._lexical_docs: list[dict[str, Any]] | None = None
        self.stats = RetrievalStats()

    @property
    def features(self) -> list[dict[str, Any]]:
        if self._features is None:
            self._features = load_features(self.features_path)
        return self._features

    @property
    def eligible_features(self) -> list[dict[str, Any]]:
        if self._eligible_features is None:
            self._eligible_features = [feature for feature in self.features if eligible_product(feature)]
        return self._eligible_features

    def lexical_indexes(self) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
        if self._token_index is not None and self._canonical_index is not None:
            return self._token_index, self._canonical_index
        token_index: dict[str, set[int]] = {}
        canonical_index: dict[str, set[int]] = {}
        for index, feature in enumerate(self.eligible_features):
            text = " ".join(
                value
                for value in (
                    feature.get("normalized_name"),
                    feature.get("canonical_name"),
                    feature.get("category"),
                    feature.get("brand"),
                )
                if value
            )
            for token in set(normalize_text(text).split()):
                token_index.setdefault(token, set()).add(index)
            canonical = feature.get("canonical_name")
            if canonical:
                canonical_index.setdefault(normalize_text(canonical), set()).add(index)
        self._token_index = token_index
        self._canonical_index = canonical_index
        return token_index, canonical_index

    @property
    def lexical_docs(self) -> list[dict[str, Any]]:
        if self._lexical_docs is None:
            docs = []
            for feature in self.eligible_features:
                normalized = feature.get("normalized_name") or ""
                canonical = feature.get("canonical_name") or ""
                candidate_text = " ".join([normalized, canonical])
                docs.append(
                    {
                        "feature": feature,
                        "normalized": normalized,
                        "canonical": canonical,
                        "tokens": set(normalize_text(candidate_text).split()),
                    }
                )
            self._lexical_docs = docs
        return self._lexical_docs

    def lexical_search_space(self, query: str) -> list[dict[str, Any]]:
        token_index, canonical_index = self.lexical_indexes()
        query_tokens = set(normalize_text(query).split())
        expanded_query_tokens = set()
        for token in query_tokens:
            expanded_query_tokens.update(token_variants(token))
        selected: set[int] = set()
        for token in expanded_query_tokens:
            selected.update(token_index.get(token, set()))
        alias_query = apply_alias(query)
        selected.update(canonical_index.get(normalize_text(query), set()))
        selected.update(canonical_index.get(normalize_text(alias_query), set()))
        for token in expanded_query_tokens:
            selected.update(canonical_index.get(token, set()))
        if not selected:
            prefix = next(iter(query_tokens), "")[:3]
            if prefix:
                for token, indexes in token_index.items():
                    if token.startswith(prefix):
                        selected.update(indexes)
        docs = self.lexical_docs
        selected_docs = [docs[index] for index in selected]
        if len(selected_docs) <= self.max_lexical_search_space:
            return selected_docs
        alias_query = apply_alias(query)
        normalized_query = normalize_text(query)
        query_tokens = set(normalized_query.split())
        expanded_query_tokens = set()
        for token in query_tokens:
            expanded_query_tokens.update(token_variants(token))

        def cheap_rank(doc: dict[str, Any]) -> tuple[float, str]:
            canonical = normalize_text(doc["canonical"] or "")
            normalized = doc["normalized"]
            tokens = doc["tokens"]
            overlap = len(expanded_query_tokens & tokens)
            token_score = overlap / len(expanded_query_tokens | tokens) if expanded_query_tokens and tokens else 0.0
            exact = normalized_query == normalized or normalized_query == canonical or alias_query == canonical
            canonical_bonus = 1.0 if canonical and canonical in {normalized_query, alias_query} else 0.0
            return (-(2.0 if exact else 0.0) - canonical_bonus - token_score, normalized)

        return sorted(selected_docs, key=cheap_rank)[: self.max_lexical_search_space]

    def gated_lexical_space(self, query, allowed_ids):
        if allowed_ids is None:
            return self.lexical_search_space(query)
        if not hasattr(self, "_lexical_doc_by_id"):
            self._lexical_doc_by_id = {doc["feature"]["product_id"]: doc for doc in self.lexical_docs}
        return [self._lexical_doc_by_id[pid] for pid in sorted(allowed_ids) if pid in self._lexical_doc_by_id]

    @staticmethod
    def allowed_vector_rows(rows, allowed_ids):
        if allowed_ids is None:
            return np.arange(len(rows))
        return np.asarray([i for i, row in enumerate(rows) if row["product_id"] in allowed_ids], dtype=np.int64)

    @staticmethod
    def safe_vector_scores(matrix, vector):
        # Float64 dot avoids backend float32 BLAS overflow/warnings on this host.
        # Non-finite input can never become positive matching evidence.
        with np.errstate(invalid="ignore", over="ignore", divide="ignore"):
            scores = np.einsum("ij,j->i", matrix.astype(np.float64), np.asarray(vector, dtype=np.float64))
        return np.where(np.isfinite(scores), np.clip(scores, -1.0, 1.0), -1.0)

    def load_index(self) -> bool:
        if self._index_embeddings is not None and self._index_metadata is not None:
            return True
        try:
            embeddings, metadata = load_existing_index(self.index_dir)
        except Exception as exc:
            self._index_error = str(exc)
            return False
        if embeddings is None or metadata is None:
            self._index_error = "Persisted vector index is missing."
            return False
        if metadata.get("model_version") != self.backend.model_version:
            self._index_error = "Persisted vector index model version does not match embedding backend."
            return False
        self._index_embeddings = normalize_vectors(embeddings)
        self._index_metadata = metadata
        return True

    def query_vector(self, text: str) -> tuple[np.ndarray | None, float | None, str | None]:
        key = (text, self.backend.model_version)
        cached = self.query_cache.get(key)
        if cached is not None:
            self.stats.cache_hits += 1
            return cached, 0.0, None
        self.stats.cache_misses += 1
        started_at = time.perf_counter()
        try:
            self.stats.encode_calls += 1
            vector = self.backend.embed([text], batch_size=1)[0]
        except Exception as exc:
            return None, None, str(exc)
        latency = round((time.perf_counter() - started_at) * 1000, 2)
        self.stats.embedding_ms += latency
        self.query_cache.set(key, vector)
        return vector, latency, None

    def query_vectors(self, texts: list[str], batch_size: int = 64) -> tuple[dict[str, np.ndarray], float | None, list[str]]:
        vectors: dict[str, np.ndarray] = {}
        missing: list[str] = []
        seen: set[str] = set()
        for text in texts:
            if text in seen:
                continue
            seen.add(text)
            key = (text, self.backend.model_version)
            cached = self.query_cache.get(key)
            if cached is not None:
                self.stats.cache_hits += 1
                vectors[text] = cached
            else:
                self.stats.cache_misses += 1
                missing.append(text)
        if not missing:
            return vectors, 0.0, []
        started_at = time.perf_counter()
        try:
            self.stats.encode_calls += 1
            batch_vectors = self.backend.embed(missing, batch_size=batch_size)
        except Exception as exc:
            return vectors, None, [str(exc)]
        latency = round((time.perf_counter() - started_at) * 1000, 2)
        self.stats.embedding_ms += latency
        for text, vector in zip(missing, batch_vectors):
            self.query_cache.set((text, self.backend.model_version), vector)
            vectors[text] = vector
        return vectors, latency, []

    def retrieve_product_candidates(
        self,
        ingredient_text: str,
        limit: int = 30,
        use_semantic: bool = True,
        allowed_product_ids: set[str] | None = None,
    ) -> CandidateRetrievalResult:
        started_at = time.perf_counter()
        normalized_query, parsed = query_embedding_text(ingredient_text)
        query_category, _ = infer_category(normalized_query)
        errors = []

        lexical_started = time.perf_counter()
        self.stats.lexical_searches += 1
        lexical_space = self.gated_lexical_space(normalized_query, allowed_product_ids)
        lexical = lexical_candidates(lexical_space, normalized_query, parsed, query_category, limit=max(80, limit * 3))
        lexical_latency = round((time.perf_counter() - lexical_started) * 1000, 2)
        self.stats.lexical_ms += lexical_latency

        semantic_candidates = []
        semantic_latency = None
        query_embedding_latency = None
        index_available = self.load_index() if use_semantic else False
        semantic_failed = False
        if index_available:
            vector, query_embedding_latency, error = self.query_vector(normalized_query)
            if error:
                errors.append(error)
                semantic_failed = True
            elif vector is not None:
                semantic_started = time.perf_counter()
                self.stats.vector_searches += 1
                rows = self._index_metadata.get("rows") or []
                row_ids = self.allowed_vector_rows(rows, allowed_product_ids)
                scores = self.safe_vector_scores(self._index_embeddings[row_ids], vector)
                top_count = min(max(80, limit * 3), len(scores))
                if top_count:
                    top_indices = np.argpartition(-scores, top_count - 1)[:top_count]
                    top_indices = top_indices[np.lexsort((top_indices, -scores[top_indices]))]
                    rows = self._index_metadata.get("rows") or []
                    for rank, local_index in enumerate(top_indices):
                        index = row_ids[local_index]
                        if index >= len(rows):
                            continue
                        row = rows[int(index)]
                        semantic_candidates.append(
                            Candidate(
                                product_id=row["product_id"],
                                original_product_name=row.get("original_product_name") or row["normalized_name"],
                                normalized_name=row["normalized_name"],
                                record_status=row.get("record_status"),
                                canonical_ingredient=row.get("canonical_name"),
                                semantic_similarity=round(float(scores[local_index]), 4),
                                category_match_signal=category_signal(query_category, row.get("category")),
                                retrieval_reason_codes=["semantic_vector"],
                                source_rank=rank,
                            )
                        )
                semantic_latency = round((time.perf_counter() - semantic_started) * 1000, 2)
                self.stats.vector_ms += semantic_latency
        elif not use_semantic:
            errors.append("Semantic retrieval skipped while embedding model warms up.")
        else:
            errors.append(self._index_error or "Persisted vector index unavailable.")

        merged = merge_candidates(lexical, semantic_candidates, limit=limit)
        total_latency = round((time.perf_counter() - started_at) * 1000, 2)
        return CandidateRetrievalResult(
            ingredient_text=ingredient_text,
            parsed_query=parsed,
            normalized_semantic_query=normalized_query,
            candidates=merged,
            retrieval_latency_ms=total_latency,
            lexical_latency_ms=lexical_latency,
            semantic_latency_ms=semantic_latency,
            query_embedding_latency_ms=query_embedding_latency,
            embedding_index_available=index_available,
            embedding_model_version=self.backend.model_version if index_available else None,
            index_version=(self._index_metadata or {}).get("index_version") if index_available else None,
            degraded_mode=not index_available or semantic_failed,
            errors=errors,
        )

    def retrieve_product_candidates_batch(
        self,
        ingredient_texts: list[str],
        limit: int = 30,
        embedding_batch_size: int = 64,
        vector_batch_size: int = 128,
        use_semantic: bool = True,
        allowed_product_ids: list[set[str]] | None = None,
    ) -> list[CandidateRetrievalResult]:
        started_at = time.perf_counter()
        if allowed_product_ids is not None and len(allowed_product_ids) != len(ingredient_texts):
            raise ValueError("one product gate is required per ingredient")
        gates = allowed_product_ids if allowed_product_ids is not None else [None] * len(ingredient_texts)
        normalized_items = [query_embedding_text(text) for text in ingredient_texts]
        normalized_queries = [item[0] for item in normalized_items]
        query_categories = [infer_category(query)[0] for query in normalized_queries]
        errors_by_query: list[list[str]] = [[] for _ in ingredient_texts]

        lexical_started = time.perf_counter()
        lexical_results = []
        for normalized_query, parsed, query_category, gate in zip(normalized_queries, [item[1] for item in normalized_items], query_categories, gates):
            self.stats.lexical_searches += 1
            lexical_space = self.gated_lexical_space(normalized_query, gate)
            lexical_results.append(lexical_candidates(lexical_space, normalized_query, parsed, query_category, limit=max(80, limit * 3)))
        lexical_total = round((time.perf_counter() - lexical_started) * 1000, 2)
        self.stats.lexical_ms += lexical_total

        semantic_results: list[list[Candidate]] = [[] for _ in ingredient_texts]
        semantic_latencies: list[float | None] = [None for _ in ingredient_texts]
        query_embedding_latency: float | None = None
        index_available = self.load_index() if use_semantic else False
        semantic_failed = False
        if index_available:
            vectors_by_text, query_embedding_latency, errors = self.query_vectors(normalized_queries, batch_size=embedding_batch_size)
            if errors:
                semantic_failed = True
                for bucket in errors_by_query:
                    bucket.extend(errors)
            rows = (self._index_metadata or {}).get("rows") or []
            jobs = [(query, frozenset(gate) if gate is not None else None) for query, gate in zip(normalized_queries, gates)]
            unique_vectors = [(job, vectors_by_text[job[0]]) for job in dict.fromkeys(jobs) if job[0] in vectors_by_text]
            semantic_by_query: dict[str, tuple[list[Candidate], float]] = {}
            top_count = min(max(80, limit * 3), len(rows))
            for offset in range(0, len(unique_vectors), vector_batch_size):
                batch = unique_vectors[offset : offset + vector_batch_size]
                if not batch or not top_count:
                    continue
                semantic_started = time.perf_counter()
                self.stats.vector_searches += 1
                for row_offset, (job, _vector) in enumerate(batch):
                    query, gate = job
                    row_ids = self.allowed_vector_rows(rows, gate)
                    scores = self.safe_vector_scores(self._index_embeddings[row_ids], _vector)
                    count = min(top_count, len(scores))
                    if not count:
                        semantic_by_query[job] = ([], 0.0)
                        continue
                    top_indices = np.argpartition(-scores, count - 1)[:count]
                    top_indices = top_indices[np.lexsort((top_indices, -scores[top_indices]))]
                    candidates = []
                    query_category = infer_category(query)[0]
                    for rank, local_index in enumerate(top_indices):
                        index = row_ids[local_index]
                        if index >= len(rows):
                            continue
                        row = rows[int(index)]
                        candidates.append(
                            Candidate(
                                product_id=row["product_id"],
                                original_product_name=row.get("original_product_name") or row["normalized_name"],
                                normalized_name=row["normalized_name"],
                                record_status=row.get("record_status"),
                                canonical_ingredient=row.get("canonical_name"),
                                semantic_similarity=round(float(scores[local_index]), 4),
                                category_match_signal=category_signal(query_category, row.get("category")),
                                retrieval_reason_codes=["semantic_vector"],
                                source_rank=rank,
                            )
                        )
                    semantic_by_query[job] = (candidates, 0.0)
                vector_latency = round((time.perf_counter() - semantic_started) * 1000, 2)
                self.stats.vector_ms += vector_latency
                for job, _vector in batch:
                    candidates, _ = semantic_by_query[job]
                    semantic_by_query[job] = (candidates, vector_latency)
            for index, job in enumerate(jobs):
                candidates, latency = semantic_by_query.get(job, ([], None))
                semantic_results[index] = candidates
                semantic_latencies[index] = latency
        elif not use_semantic:
            for bucket in errors_by_query:
                bucket.append("Semantic retrieval skipped while embedding model warms up.")
        else:
            error = self._index_error or "Persisted vector index unavailable."
            for bucket in errors_by_query:
                bucket.append(error)

        results = []
        for index, (ingredient_text, (normalized_query, parsed), query_category) in enumerate(zip(ingredient_texts, normalized_items, query_categories)):
            merged = merge_candidates(lexical_results[index], semantic_results[index], limit=limit)
            results.append(
                CandidateRetrievalResult(
                    ingredient_text=ingredient_text,
                    parsed_query=parsed,
                    normalized_semantic_query=normalized_query,
                    candidates=merged,
                    retrieval_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
                    lexical_latency_ms=lexical_total,
                    semantic_latency_ms=semantic_latencies[index],
                    query_embedding_latency_ms=query_embedding_latency,
                    embedding_index_available=index_available,
                    embedding_model_version=self.backend.model_version if index_available else None,
                    index_version=(self._index_metadata or {}).get("index_version") if index_available else None,
                    degraded_mode=not index_available or semantic_failed,
                    errors=errors_by_query[index],
                )
            )
        return results


def token_similarity(query: str, candidate: str) -> float:
    query_tokens = set(normalize_text(query).split())
    candidate_tokens = set(normalize_text(candidate).split())
    if not query_tokens or not candidate_tokens:
        return 0.0
    return len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)


def category_signal(query_category: str | None, product_category: str | None) -> str:
    if not query_category or not product_category:
        return "unknown"
    return "match" if query_category == product_category else "mismatch"


def lexical_score(query: str, feature_or_doc: dict[str, Any]) -> tuple[float, list[str], bool, bool]:
    if "feature" in feature_or_doc:
        feature = feature_or_doc["feature"]
        normalized = feature_or_doc["normalized"]
        canonical = feature_or_doc["canonical"]
        candidate_tokens = feature_or_doc["tokens"]
    else:
        feature = feature_or_doc
        normalized = feature.get("normalized_name") or ""
        canonical = feature.get("canonical_name") or ""
        candidate_text = " ".join([normalized, canonical])
        candidate_tokens = set(normalize_text(candidate_text).split())
    alias_query = apply_alias(query)
    query_tokens = set(normalize_text(query).split())
    expanded_query_tokens = set()
    for token in query_tokens:
        expanded_query_tokens.update(token_variants(token))
    exact = query == normalized or query == canonical or alias_query == canonical
    alias = alias_query != query and alias_query == canonical
    token_score = (
        len(expanded_query_tokens & candidate_tokens) / len(expanded_query_tokens | candidate_tokens)
        if expanded_query_tokens and candidate_tokens
        else 0.0
    )
    ratio = 0.0
    if exact or alias or token_score > 0 or query[:3] == normalized[:3]:
        ratio = SequenceMatcher(None, query, normalized).ratio()
    score = max(ratio, token_score)
    reasons = []
    if exact:
        score = max(score, 1.0)
        reasons.append("exact_or_canonical_match")
    if alias:
        score = max(score, 0.98)
        reasons.append("alias_match")
    if token_score > 0:
        reasons.append("token_similarity")
    if ratio >= 0.72:
        reasons.append("fuzzy_similarity")
    return round(score, 4), reasons, exact, alias


def lexical_candidates(
    features: list[dict[str, Any]],
    query: str,
    parsed: dict[str, Any],
    query_category: str | None,
    limit: int = 90,
) -> list[Candidate]:
    candidates = []
    for item in features:
        feature = item["feature"] if "feature" in item else item
        score, reasons, exact, alias = lexical_score(query, item)
        if score < 0.18 and not exact and not alias:
            continue
        category_match = category_signal(query_category, feature.get("category"))
        candidates.append(
            Candidate(
                product_id=feature["product_id"],
                original_product_name=feature.get("original_product_name") or feature.get("normalized_name"),
                normalized_name=feature.get("normalized_name"),
                record_status=feature.get("record_status"),
                canonical_ingredient=feature.get("canonical_name"),
                lexical_similarity=score,
                exact_match=exact,
                alias_match=alias,
                category_match_signal=category_match,
                retrieval_reason_codes=reasons or ["lexical_similarity"],
                source_rank=None,
            )
        )
    candidates.sort(key=lambda item: (-item.lexical_similarity, item.category_match_signal != "match", item.normalized_name))
    for rank, candidate in enumerate(candidates[:limit]):
        candidate.source_rank = rank
    return candidates[:limit]


def merge_candidates(lexical: list[Candidate], semantic: list[Candidate], limit: int) -> list[Candidate]:
    by_id: dict[str, Candidate] = {}
    for candidate in lexical + semantic:
        existing = by_id.get(candidate.product_id)
        if existing is None:
            by_id[candidate.product_id] = candidate
            continue
        existing.lexical_similarity = max(existing.lexical_similarity, candidate.lexical_similarity)
        if candidate.semantic_similarity is not None:
            existing.semantic_similarity = max(existing.semantic_similarity or -1, candidate.semantic_similarity)
        existing.exact_match = existing.exact_match or candidate.exact_match
        existing.alias_match = existing.alias_match or candidate.alias_match
        existing.retrieval_reason_codes = sorted(
            set(existing.retrieval_reason_codes) | set(candidate.retrieval_reason_codes)
        )
        if existing.category_match_signal == "unknown":
            existing.category_match_signal = candidate.category_match_signal

    def rank_score(candidate: Candidate) -> tuple[float, float, int, str]:
        semantic = candidate.semantic_similarity if candidate.semantic_similarity is not None else 0.0
        exact_bonus = 1 if candidate.exact_match or candidate.alias_match else 0
        category_bonus = 1 if candidate.category_match_signal == "match" else 0
        combined = candidate.lexical_similarity * 0.62 + semantic * 0.38 + exact_bonus * 0.2 + category_bonus * 0.05
        return (-combined, -(candidate.semantic_similarity or 0), candidate.source_rank or 999999, candidate.normalized_name)

    return sorted(by_id.values(), key=rank_score)[:limit]


_retriever_singleton: ProductCandidateRetriever | None = None


def get_product_candidate_retriever() -> ProductCandidateRetriever:
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = ProductCandidateRetriever()
    return _retriever_singleton


def retrieve_product_candidates(ingredient_text: str, limit: int = 30) -> CandidateRetrievalResult:
    return get_product_candidate_retriever().retrieve_product_candidates(ingredient_text, limit=limit)
