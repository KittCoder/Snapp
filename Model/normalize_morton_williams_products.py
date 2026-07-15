import argparse
import csv
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ingredient_normalization import (
    FEATURE_EXTRACTION_VERSION,
    MALFORMED_RECORD,
    PROBABLE_PRODUCT,
    SCRAPER_NOISE,
    VALID_PRODUCT,
    extract_product_features,
)


MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = MODEL_DIR / "database.merged.json"
DEFAULT_OUTPUT = MODEL_DIR / "morton_williams_product_features.json"
DEFAULT_UNCERTAIN_LOG = MODEL_DIR / "morton_williams_uncertain_products.csv"
DEFAULT_INVALID_LOG = MODEL_DIR / "morton_williams_invalid_or_noise.csv"


def load_products(path):
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)
    products = data.get("products") if isinstance(data, dict) else data
    if not isinstance(products, list):
        raise ValueError(f"{path} does not contain a products list")
    return products


def atomic_write_json(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")
        temp_name = file.name
    os.replace(temp_name, path)


def write_csv(records, path, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        temp_name = file.name
    os.replace(temp_name, path)


def has_meaningful_attribute(feature):
    fields = (
        "form",
        "fat_level",
        "salted_status",
        "sweetened_status",
        "freshness",
        "cut",
        "bone_status",
        "skin_status",
    )
    return any(feature.get(field) for field in fields) or bool(feature.get("dietary_attributes"))


def coverage(features):
    total = len(features) or 1
    return {
        "normalized_name": round(sum(bool(f.get("normalized_name")) for f in features) / total * 100, 2),
        "price": round(sum(f.get("price") is not None for f in features) / total * 100, 2),
        "package_quantity": round(sum(f.get("package_quantity") is not None for f in features) / total * 100, 2),
        "package_unit": round(sum(bool(f.get("package_unit")) for f in features) / total * 100, 2),
        "brand": round(sum(bool(f.get("brand")) for f in features) / total * 100, 2),
        "category": round(sum(bool(f.get("category")) for f in features) / total * 100, 2),
        "form": round(sum(bool(f.get("form")) for f in features) / total * 100, 2),
        "meaningful_attributes": round(sum(has_meaningful_attribute(f) for f in features) / total * 100, 2),
        "canonical_ingredient": round(sum(bool(f.get("canonical_name")) for f in features) / total * 100, 2),
        "valid_product_classification": round(
            sum(f.get("record_status") == VALID_PRODUCT for f in features) / total * 100,
            2,
        ),
    }


def build_feature_payload(products, *, limit=None):
    features = []
    uncertain = []
    invalid_or_noise = []
    seen_ids = set()
    seen_fingerprints = set()
    max_count = len(products) if limit is None else min(limit, len(products))
    for index, product in enumerate(products[:max_count]):
        if not isinstance(product, dict):
            product = {}
        feature = extract_product_features(product, index, seen_fingerprints)
        if feature["product_id"] in seen_ids:
            continue
        seen_ids.add(feature["product_id"])
        features.append(feature)

        if feature.get("uncertainty_reasons") and feature.get("eligible_for_retrieval"):
            uncertain.append(
                {
                    "product_id": feature["product_id"],
                    "name": product.get("name") or product.get("product_name") or "",
                    "price": product.get("price") or "",
                    "unit": product.get("unit") or product.get("package_size") or "",
                    "record_status": feature.get("record_status"),
                    "reason": "; ".join(feature["uncertainty_reasons"]),
                }
            )
        if feature.get("record_status") in {SCRAPER_NOISE, MALFORMED_RECORD}:
            invalid_or_noise.append(
                {
                    "product_id": feature["product_id"],
                    "name": product.get("name") or product.get("product_name") or "",
                    "price": product.get("price") or "",
                    "unit": product.get("unit") or product.get("package_size") or "",
                    "record_status": feature.get("record_status"),
                    "source_quality_score": feature.get("source_quality_score"),
                    "exclusion_reasons": "; ".join(feature.get("exclusion_reasons") or []),
                }
            )
    canonical_ingredients = sorted(
        {
            feature["canonical_name"]
            for feature in features
            if feature.get("canonical_name") and feature.get("eligible_for_retrieval")
        }
    )
    status_counts = Counter(feature.get("record_status") for feature in features)
    uncertainty_counts = Counter(
        reason
        for feature in features
        for reason in feature.get("uncertainty_reasons", [])
    )
    eligible_features = [feature for feature in features if feature.get("eligible_for_retrieval")]
    return {
        "metadata": {
            "source": "Morton Williams product feature extraction",
            "input_product_count": len(products),
            "feature_count": len(features),
            "uncertain_count": len(uncertain),
            "invalid_or_noise_count": len(invalid_or_noise),
            "canonical_ingredient_count": len(canonical_ingredients),
            "record_status_counts": dict(status_counts),
            "uncertainty_reason_counts": dict(uncertainty_counts),
            "feature_coverage_percentages": coverage(features),
            "eligible_feature_coverage_percentages": coverage(eligible_features),
            "feature_extraction_version": FEATURE_EXTRACTION_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "canonical_ingredients": [
            {"canonical_name": canonical_name}
            for canonical_name in canonical_ingredients
        ],
        "features": features,
    }, uncertain, invalid_or_noise


def main():
    parser = argparse.ArgumentParser(
        description="Normalize Morton Williams products and extract deterministic matching features."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--uncertain-log", default=str(DEFAULT_UNCERTAIN_LOG))
    parser.add_argument("--invalid-log", default=str(DEFAULT_INVALID_LOG))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    products = load_products(args.input)
    payload, uncertain, invalid_or_noise = build_feature_payload(products, limit=args.limit)
    atomic_write_json(payload, args.output)
    write_csv(
        uncertain,
        args.uncertain_log,
        ["product_id", "name", "price", "unit", "record_status", "reason"],
    )
    write_csv(
        invalid_or_noise,
        args.invalid_log,
        ["product_id", "name", "price", "unit", "record_status", "source_quality_score", "exclusion_reasons"],
    )
    print(
        f"Wrote {payload['metadata']['feature_count']} feature rows to {args.output}; "
        f"{len(uncertain)} uncertain rows logged to {args.uncertain_log}; "
        f"{len(invalid_or_noise)} invalid/noise rows logged to {args.invalid_log}."
    )
    print(f"Record statuses: {payload['metadata']['record_status_counts']}")
    print(f"Uncertainty reasons: {payload['metadata']['uncertainty_reason_counts']}")


if __name__ == "__main__":
    main()
