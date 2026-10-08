#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1] / "Model"
sys.path.insert(0, str(MODEL_DIR))

from recipe_search_typesense import DEFAULT_CORPUS_PATH, DEFAULT_EXPORT_PATH, export_documents  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export SNAPP recipe corpus as Typesense JSONL documents.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT_PATH)
    args = parser.parse_args()

    summary = export_documents(args.corpus, args.output)
    print(f"Processed source recipes: {summary['processed']}")
    print(f"Unique document IDs: {summary['unique_document_ids']}")
    print(f"Output: {summary['export_path']}")
    if summary["duplicate_ids"]:
        print(f"Duplicate IDs: {len(summary['duplicate_ids'])}")
        for document_id in summary["duplicate_ids"][:20]:
            print(f"  {document_id}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
