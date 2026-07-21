from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from artifact_manifest import DEFAULT_MANIFEST_PATH, validate_runtime_artifacts, write_manifest
from ops_metrics import log_event, metrics


MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = MODEL_DIR / os.getenv("SNAPP_GROCERY_DB_FILENAME", "database.scrape-20260721-143928.json")
DEFAULT_FEATURES = MODEL_DIR / "morton_williams_product_features.json"
DEFAULT_UNCERTAIN = MODEL_DIR / "morton_williams_uncertain_products.csv"
DEFAULT_INVALID = MODEL_DIR / "morton_williams_invalid_or_noise.csv"
DEFAULT_INDEX_DIR = MODEL_DIR / "morton_williams_vector_index"
ROLLBACK_DIR = MODEL_DIR / "artifact_rollbacks"


def run_step(command: list[str], *, dry_run: bool = False) -> None:
    log_event("artifact_refresh_step", command=" ".join(command), dry_run=dry_run)
    if dry_run:
        return
    subprocess.run(command, check=True, cwd=MODEL_DIR.parent)


def copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def backup_active_artifacts() -> Path:
    backup = ROLLBACK_DIR / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    copy_if_exists(DEFAULT_FEATURES, backup / DEFAULT_FEATURES.name)
    copy_if_exists(DEFAULT_UNCERTAIN, backup / DEFAULT_UNCERTAIN.name)
    copy_if_exists(DEFAULT_INVALID, backup / DEFAULT_INVALID.name)
    copy_if_exists(DEFAULT_INDEX_DIR, backup / DEFAULT_INDEX_DIR.name)
    copy_if_exists(DEFAULT_MANIFEST_PATH, backup / DEFAULT_MANIFEST_PATH.name)
    return backup


def promote_file(staged: Path, active: Path) -> None:
    if active.exists():
        active.unlink()
    os.replace(staged, active)


def promote_dir(staged: Path, active: Path) -> None:
    temp_old = active.with_name(f"{active.name}.old-{int(time.time())}")
    if active.exists():
        os.replace(active, temp_old)
    try:
        os.replace(staged, active)
    except Exception:
        if temp_old.exists():
            os.replace(temp_old, active)
        raise
    if temp_old.exists():
        shutil.rmtree(temp_old)


def validate_source_schema(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    products = payload.get("products") if isinstance(payload, dict) else payload
    if not isinstance(products, list):
        raise ValueError("Morton Williams source must be a list or an object with products")
    if not products:
        raise ValueError("Morton Williams source contains no products")
    if not any(isinstance(row, dict) and (row.get("name") or row.get("product_name")) for row in products[:100]):
        raise ValueError("Morton Williams source does not expose product names in the expected fields")
    return {"product_rows": len(products)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely refresh Morton Williams matcher artifacts.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--deterministic-test-embeddings", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    staging_root = Path(tempfile.mkdtemp(prefix="snapp-mw-refresh-"))
    staged_features = staging_root / DEFAULT_FEATURES.name
    staged_uncertain = staging_root / DEFAULT_UNCERTAIN.name
    staged_invalid = staging_root / DEFAULT_INVALID.name
    staged_index = staging_root / DEFAULT_INDEX_DIR.name
    staged_manifest = staging_root / DEFAULT_MANIFEST_PATH.name
    try:
        source_summary = validate_source_schema(args.source)
        log_event("artifact_refresh_source_validated", **source_summary)
        backup = backup_active_artifacts() if not args.dry_run else None
        normalize_cmd = [
            sys.executable,
            str(MODEL_DIR / "normalize_morton_williams_products.py"),
            "--input",
            str(args.source),
            "--output",
            str(staged_features),
            "--uncertain-log",
            str(staged_uncertain),
            "--invalid-log",
            str(staged_invalid),
        ]
        run_step(normalize_cmd, dry_run=args.dry_run)
        index_cmd = [
            sys.executable,
            str(MODEL_DIR / "build_product_embedding_index.py"),
            "--features",
            str(staged_features),
            "--index-dir",
            str(staged_index),
        ]
        if args.deterministic_test_embeddings:
            index_cmd.append("--deterministic-test-embeddings")
        if args.force_rebuild and staged_index.exists():
            shutil.rmtree(staged_index)
        run_step(index_cmd, dry_run=args.dry_run)
        if not args.dry_run:
            write_manifest(
                path=staged_manifest,
                source_path=args.source,
                features_path=staged_features,
                index_dir=staged_index,
                generation_command=" ".join(sys.argv),
            )
            validation = validate_runtime_artifacts(
                manifest_path=staged_manifest,
                source_path=args.source,
                features_path=staged_features,
                index_dir=staged_index,
            )
            if not validation.ok:
                raise RuntimeError("; ".join(validation.errors))
            if not args.skip_tests:
                run_step([sys.executable, "-m", "unittest", "discover", "-s", str(MODEL_DIR / "tests"), "-v"])
                run_step([sys.executable, str(MODEL_DIR / "evaluate_product_matching.py"), "--fixture", str(MODEL_DIR / "evaluation" / "product_match_cases.jsonl")])
            promote_file(staged_features, DEFAULT_FEATURES)
            promote_file(staged_uncertain, DEFAULT_UNCERTAIN)
            promote_file(staged_invalid, DEFAULT_INVALID)
            promote_dir(staged_index, DEFAULT_INDEX_DIR)
            promote_file(staged_manifest, DEFAULT_MANIFEST_PATH)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        metrics.increment("artifact_refresh_success")
        log_event("artifact_refresh_complete", elapsed_ms=elapsed_ms, dry_run=args.dry_run)
        print(json.dumps({"status": "ok", "dry_run": args.dry_run, "backup": str(backup) if not args.dry_run else None, "elapsed_ms": elapsed_ms}, indent=2))
    except Exception as exc:
        metrics.increment("artifact_refresh_failure")
        log_event("artifact_refresh_failed", error_type=type(exc).__name__)
        print(json.dumps({"status": "failed", "error": str(exc), "active_artifacts_unchanged": True}, indent=2), file=sys.stderr)
        raise SystemExit(1)
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)


if __name__ == "__main__":
    main()
