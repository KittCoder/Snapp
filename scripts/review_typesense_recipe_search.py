#!/usr/bin/env python3
import argparse
import json
import statistics
import sys
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1] / "Model"
sys.path.insert(0, str(MODEL_DIR))

from recipe_search_typesense import DEFAULT_REVIEW_PATH, TypesenseConfig, TypesenseUnavailable, search_recipes  # noqa: E402


BENCHMARK_QUERIES = [
    "warm winter meal with beef",
    "healthy chicken dinner",
    "vegetarian breakfast under 15 minutes",
    "something creamy but dairy free",
    "cheap pasta dinner for four",
    "spicy meal with rice",
    "something like tacos but vegetarian",
    "chicken dinner without cheese",
    "quick breakfast with eggs",
    "beef recipe under 30 minutes",
    "something with potatoes and chicken",
    "pasta without tomato",
    "quick lunch",
    "rice and beans",
    "something with salmon",
    "easy egg breakfast",
    "dinner with ground beef",
    "vegetarian pasta",
    "chicken and rice under 30 minutes",
    "breakfast without eggs",
    "soup with lentils",
    "dessert with apples",
    "quick side dish with potatoes",
    "pork dinner under 45 minutes",
    "fish dinner with lemon",
    "beans without pork",
    "no bake dessert",
    "casserole with chicken",
    "vegetarian rice dinner",
    "sandwich with turkey",
    "salad with chicken",
    "breakfast with oats",
    "dinner without dairy",
    "pasta with sausage",
    "potato soup",
    "tacos without beef",
    "spicy chicken",
    "quick dessert under 20 minutes",
    "rice bowl with tofu",
    "beef stew",
    "shrimp with pasta",
    "vegetable soup",
    "egg dish under 30 minutes",
    "chicken without cream",
    "slow cooker beef",
    "appetizer with cheese",
    "side dish without eggs",
    "salmon under 30 minutes",
    "beans and rice dinner",
    "breakfast with potatoes",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run manual relevance benchmark queries against Typesense.")
    parser.add_argument("--output", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    config = TypesenseConfig(timeout_seconds=10.0)
    reviews = []
    latencies = []
    for query in BENCHMARK_QUERIES:
        try:
            result = search_recipes(query, limit=args.limit, config=config, mode="keyword")
        except TypesenseUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 2
        latencies.append(result["total_latency_ms"])
        reviews.append(
            {
                "query": query,
                "parsed_constraints": result["parsed_constraints"],
                "state": result["state"],
                "latency_ms": result["total_latency_ms"],
                "typesense_latency_ms": result["typesense_latency_ms"],
                "top_10_results": result["results"][:10],
            }
        )

    artifact = {
        "query_count": len(BENCHMARK_QUERIES),
        "median_latency_ms": round(statistics.median(latencies), 2),
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 2),
        "queries": reviews,
    }
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Saved {len(BENCHMARK_QUERIES)} query reviews to {args.output}")
    print(f"Median latency ms: {artifact['median_latency_ms']}")
    print(f"P95 latency ms: {artifact['p95_latency_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
