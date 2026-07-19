from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from basket_quantity import OPTIMIZER_VERSION
from ingredient_normalization import FEATURE_EXTRACTION_VERSION
from product_compatibility import DEFAULT_OVERRIDES_PATH, MATCHER_VERSION, OverrideStore
from product_retrieval import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_INDEX_DIR,
    DEFAULT_MODEL_NAME,
    EMBEDDINGS_FILENAME,
    INDEX_VERSION,
    METADATA_FILENAME,
    eligible_product,
)


MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_PATH = MODEL_DIR / "database.merged.json"
DEFAULT_MANIFEST_PATH = MODEL_DIR / "runtime_artifact_manifest.json"
MANIFEST_SCHEMA_VERSION = "snapp-runtime-artifacts-v1"
MIN_COMPATIBLE_APP_VERSION = "phase-5"


@dataclass
class ValidationResult:
    ok: bool
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest: dict[str, Any] | None = None

    def safe_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        manifest = payload.get("manifest") or {}
        payload["manifest"] = {
            key: manifest.get(key)
            for key in (
                "schema_version",
                "product_source_version",
                "product_row_count",
                "eligible_product_count",
                "normalized_feature_version",
                "embedding_model_name",
                "embedding_dimension",
                "embedding_index_version",
                "vector_row_count",
                "matcher_version",
                "optimizer_version",
                "override_version",
                "build_timestamp",
                "minimum_compatible_application_version",
            )
            if key in manifest
        }
        return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def product_source_count(path: Path) -> int:
    if not path.exists():
        return 0
    payload = load_json(path)
    products = payload.get("products") if isinstance(payload, dict) else payload
    return len(products) if isinstance(products, list) else 0


def feature_payload(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = load_json(path)
    return payload.get("features") or [], payload.get("metadata") or {}


def override_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return sha256_file(path)


def build_runtime_manifest(
    *,
    source_path: Path = DEFAULT_SOURCE_PATH,
    features_path: Path = DEFAULT_FEATURES_PATH,
    index_dir: Path = DEFAULT_INDEX_DIR,
    overrides_path: Path = DEFAULT_OVERRIDES_PATH,
    generation_command: str | None = None,
) -> dict[str, Any]:
    features, feature_metadata = feature_payload(features_path)
    eligible = [feature for feature in features if eligible_product(feature)]
    index_metadata_path = index_dir / METADATA_FILENAME
    embeddings_path = index_dir / EMBEDDINGS_FILENAME
    index_metadata = load_json(index_metadata_path)
    embeddings = np.load(embeddings_path, mmap_mode="r")
    overrides = OverrideStore(overrides_path)
    _ = overrides.data
    index_hash = hashlib.sha256(
        (
            sha256_file(index_metadata_path)
            + ":"
            + sha256_file(embeddings_path)
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "product_source_version": source_path.name if source_path.exists() else "external-or-unavailable",
        "product_source_hash": sha256_file(source_path) if source_path.exists() else None,
        "product_row_count": product_source_count(source_path),
        "eligible_product_count": len(eligible),
        "normalized_feature_version": feature_metadata.get("feature_extraction_version") or FEATURE_EXTRACTION_VERSION,
        "normalized_feature_hash": sha256_file(features_path),
        "normalized_feature_count": len(features),
        "embedding_model_name": index_metadata.get("model_version") or DEFAULT_MODEL_NAME,
        "embedding_dimension": int(index_metadata.get("embedding_dimension") or (embeddings.shape[1] if embeddings.ndim == 2 else 0)),
        "embedding_index_version": index_metadata.get("index_version") or INDEX_VERSION,
        "vector_row_count": int(index_metadata.get("row_count") or (embeddings.shape[0] if embeddings.ndim == 2 else 0)),
        "index_hash": index_hash,
        "matcher_version": MATCHER_VERSION,
        "optimizer_version": OPTIMIZER_VERSION,
        "override_version": overrides.version,
        "override_hash": override_hash(overrides_path),
        "build_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generation_command": generation_command or " ".join(os.sys.argv),
        "minimum_compatible_application_version": MIN_COMPATIBLE_APP_VERSION,
    }


def validate_runtime_artifacts(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    source_path: Path = DEFAULT_SOURCE_PATH,
    features_path: Path = DEFAULT_FEATURES_PATH,
    index_dir: Path = DEFAULT_INDEX_DIR,
    overrides_path: Path = DEFAULT_OVERRIDES_PATH,
    require_manifest: bool = True,
    expected_model_name: str = DEFAULT_MODEL_NAME,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = None
    if not manifest_path.exists():
        message = f"runtime manifest is missing: {manifest_path.name}"
        if require_manifest:
            errors.append(message)
        else:
            warnings.append(message)
    else:
        try:
            manifest = load_json(manifest_path)
        except Exception as exc:
            errors.append(f"runtime manifest could not be parsed: {exc}")

    for label, path in (
        ("normalized features", features_path),
        ("index metadata", index_dir / METADATA_FILENAME),
        ("index embeddings", index_dir / EMBEDDINGS_FILENAME),
        ("overrides", overrides_path),
    ):
        if not path.exists():
            errors.append(f"{label} file is missing")
    if errors:
        return ValidationResult(False, "failed", errors, warnings, manifest)

    try:
        features, feature_metadata = feature_payload(features_path)
        eligible = [feature for feature in features if eligible_product(feature)]
    except Exception as exc:
        return ValidationResult(False, "failed", [f"feature artifact could not be parsed: {exc}"], warnings, manifest)

    try:
        index_metadata = load_json(index_dir / METADATA_FILENAME)
        embeddings = np.load(index_dir / EMBEDDINGS_FILENAME, mmap_mode="r")
    except Exception as exc:
        return ValidationResult(False, "failed", [f"vector index could not be loaded: {exc}"], warnings, manifest)

    rows = index_metadata.get("rows") or []
    if embeddings.ndim != 2:
        errors.append("embedding matrix must be two-dimensional")
    if index_metadata.get("row_count") != len(rows):
        errors.append("index metadata row_count does not match row metadata length")
    if embeddings.ndim == 2 and embeddings.shape[0] != len(rows):
        errors.append("embedding row count does not match index metadata rows")
    if len(rows) != len(eligible):
        errors.append("eligible feature count does not match vector row count")
    if embeddings.ndim == 2 and int(index_metadata.get("embedding_dimension") or 0) != embeddings.shape[1]:
        errors.append("embedding dimension metadata does not match matrix shape")
    if index_metadata.get("model_version") != expected_model_name:
        errors.append("index model version does not match configured embedding model")
    if index_metadata.get("index_version") != INDEX_VERSION:
        errors.append("index version is stale or unsupported")

    feature_ids = {feature.get("product_id") for feature in eligible}
    row_ids = [row.get("product_id") for row in rows]
    if set(row_ids) != feature_ids:
        errors.append("product IDs in feature artifact and vector index differ")
    if len(row_ids) != len(set(row_ids)):
        errors.append("vector index contains duplicate product IDs")

    overrides = OverrideStore(overrides_path)
    _ = overrides.data
    if overrides.load_error:
        errors.append(f"override data is invalid: {overrides.load_error}")

    if manifest:
        if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            errors.append("runtime manifest schema version is unsupported")
        checks = {
            "normalized_feature_hash": sha256_file(features_path),
            "embedding_model_name": index_metadata.get("model_version"),
            "embedding_dimension": int(index_metadata.get("embedding_dimension") or 0),
            "embedding_index_version": index_metadata.get("index_version"),
            "vector_row_count": len(rows),
            "eligible_product_count": len(eligible),
            "matcher_version": MATCHER_VERSION,
            "optimizer_version": OPTIMIZER_VERSION,
            "override_version": overrides.version,
            "override_hash": override_hash(overrides_path),
        }
        if source_path.exists() and manifest.get("product_source_hash") != sha256_file(source_path):
            errors.append("product source hash does not match manifest")
        if manifest.get("normalized_feature_version") != (feature_metadata.get("feature_extraction_version") or FEATURE_EXTRACTION_VERSION):
            errors.append("normalized feature version does not match feature artifact")
        for key, value in checks.items():
            if manifest.get(key) != value:
                errors.append(f"{key} does not match manifest")

    return ValidationResult(not errors, "ready" if not errors else "failed", errors, warnings, manifest)


def write_manifest(path: Path = DEFAULT_MANIFEST_PATH, **kwargs: Any) -> dict[str, Any]:
    manifest = build_runtime_manifest(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, sort_keys=True)
        file.write("\n")
    return manifest


def main() -> None:
    manifest = write_manifest(generation_command=" ".join(os.sys.argv))
    result = validate_runtime_artifacts(require_manifest=True)
    print(json.dumps({"manifest": manifest, "validation": result.safe_dict()}, indent=2, sort_keys=True))
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
