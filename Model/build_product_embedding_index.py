import argparse
import json
import os
import time
from pathlib import Path

from product_retrieval import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_INDEX_DIR,
    DeterministicEmbeddingBackend,
    SentenceTransformerEmbeddingBackend,
    build_product_index,
)
from artifact_manifest import DEFAULT_MANIFEST_PATH, write_manifest


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main():
    parser = argparse.ArgumentParser(
        description="Build the local Morton Williams product embedding index."
    )
    parser.add_argument("--features", default=str(DEFAULT_FEATURES_PATH))
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR))
    parser.add_argument("--model", default=os.getenv("SNAPP_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--failed-log", default=str(Path(DEFAULT_INDEX_DIR) / "failed_rows.csv"))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--source", default=str(Path(__file__).with_name("database.merged.json")))
    parser.add_argument(
        "--deterministic-test-embeddings",
        action="store_true",
        help="Use deterministic local test embeddings; intended for tests and offline smoke checks only.",
    )
    args = parser.parse_args()

    backend = (
        DeterministicEmbeddingBackend()
        if args.deterministic_test_embeddings
        else SentenceTransformerEmbeddingBackend(args.model)
    )
    started_at = time.perf_counter()
    metadata = build_product_index(
        features_path=Path(args.features),
        index_dir=Path(args.index_dir),
        backend=backend,
        batch_size=max(1, args.batch_size),
        failed_log_path=Path(args.failed_log),
    )
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    summary = {
        "index_dir": args.index_dir,
        "row_count": metadata["row_count"],
        "embedding_dimension": metadata["embedding_dimension"],
        "model_version": metadata["model_version"],
        "index_version": metadata["index_version"],
        "skipped_unchanged": metadata["skipped_unchanged"],
        "rebuilt_vectors": metadata["rebuilt_vectors"],
        "failed_rows": metadata["failed_rows"],
        "build_time_ms": elapsed_ms,
        "index_size_bytes": directory_size(Path(args.index_dir)),
    }
    manifest = write_manifest(
        path=Path(args.manifest),
        source_path=Path(args.source),
        features_path=Path(args.features),
        index_dir=Path(args.index_dir),
        generation_command=" ".join(os.sys.argv),
    )
    summary["manifest_path"] = args.manifest
    summary["manifest_schema_version"] = manifest["schema_version"]
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
