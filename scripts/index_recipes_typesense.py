#!/usr/bin/env python3
import argparse
import os
import json
import time
import sys
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1] / "Model"
sys.path.insert(0, str(MODEL_DIR))

from recipe_search_typesense import (  # noqa: E402
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    DEFAULT_CORPUS_PATH,
    DEFAULT_EXPORT_PATH,
    DEFAULT_TYPESENSE_COLLECTION,
    DEFAULT_TYPESENSE_HOST,
    DEFAULT_TYPESENSE_PORT,
    DEFAULT_TYPESENSE_PROTOCOL,
    TypesenseConfig,
    TypesenseUnavailable,
    export_documents,
    import_documents,
    recreate_collection,
)


def config_from_env(args) -> TypesenseConfig:
    return TypesenseConfig(
        host=args.host or DEFAULT_TYPESENSE_HOST,
        port=str(args.port or DEFAULT_TYPESENSE_PORT),
        protocol=args.protocol or DEFAULT_TYPESENSE_PROTOCOL,
        api_key=args.api_key or os.getenv("TYPESENSE_API_KEY", ""),
        collection=args.collection or DEFAULT_TYPESENSE_COLLECTION,
        timeout_seconds=args.timeout,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and index the SNAPP recipe Typesense collection.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--documents", type=Path, default=DEFAULT_EXPORT_PATH)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--protocol")
    parser.add_argument("--api-key")
    parser.add_argument("--collection")
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--report", type=Path, default=Path("typesense_recipe_indexing_report.json"))
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.skip_export:
        if not args.documents.exists():
            print(f"Document export does not exist: {args.documents}", file=sys.stderr)
            return 1
        processed = sum(1 for line in args.documents.open(encoding="utf-8") if line.strip())
        summary = {"processed": processed, "unique_document_ids": processed, "duplicate_ids": []}
    else:
        summary = export_documents(args.corpus, args.documents)

    print(f"Source recipes processed: {summary['processed']}")
    print(f"Unique document IDs expected: {summary['unique_document_ids']}")
    if summary["duplicate_ids"]:
        print(f"Duplicate document IDs found: {len(summary['duplicate_ids'])}", file=sys.stderr)
        return 1
    if args.dry_run:
        print("Dry run complete. Typesense was not contacted.")
        return 0

    config = config_from_env(args)
    started = time.perf_counter()
    try:
        recreate_collection(config)
        result = import_documents(config, args.documents)
    except TypesenseUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result.update(embedding_model=EMBEDDING_MODEL, embedding_dimension=EMBEDDING_DIMENSION,
                  total_indexing_ms=round((time.perf_counter() - started) * 1000, 2))
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Documents indexed: {result['successes']}")
    print(f"Indexing latency ms: {result['elapsed_ms']}")
    if result["failures"]:
        print(f"Indexing failures: {len(result['failures'])}", file=sys.stderr)
        for failure in result["failures"][:50]:
            print(f"  line={failure.get('line')} error={failure.get('error')}", file=sys.stderr)
        return 1
    if result["successes"] != summary["processed"]:
        print("Indexed document count did not match processed source recipe count.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
