from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from basket_quantity import BasketBuilder
from matcher_warmup import warmup_matcher, warmup_status


RECIPES_PATH = Path(__file__).resolve().parent / "USDA recipes.json"


def rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return round(usage / (1024 * 1024), 2)
    return round(usage / 1024, 2)


def load_recipes(count: int) -> list[dict[str, object]]:
    data = json.loads(RECIPES_PATH.read_text(encoding="utf-8"))["recipes"][:count]
    recipes = []
    for recipe in data:
        ingredients = []
        for ingredient in recipe.get("ingredients") or []:
            raw = ingredient.get("raw") if isinstance(ingredient, dict) else str(ingredient)
            if raw and raw.strip():
                ingredients.append(raw.strip())
        recipes.append({"id": recipe.get("id") or recipe.get("name"), "name": recipe.get("name"), "ingredients": ingredients})
    return recipes


def stats_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    return {key: round(after[key] - before.get(key, 0), 2) for key in after}


def run_basket(builder: BasketBuilder, recipes: list[dict[str, object]], label: str) -> dict[str, object]:
    retriever = builder.match_service.retriever
    before = retriever.stats.to_dict()
    started = time.perf_counter()
    basket = builder.build_multi_recipe_basket(recipes)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    after = retriever.stats.to_dict()
    return {
        "label": label,
        "recipes": len(recipes),
        "raw_ingredient_lines": sum(len(recipe["ingredients"]) for recipe in recipes),
        "basket_items": len(basket.shopping_basket),
        "latency_ms": elapsed,
        "checkout_cost": basket.checkout_cost,
        "effective_ingredient_cost": basket.effective_ingredient_cost,
        "retrieval_stats": stats_delta(before, after),
        "match_cache_size": len(builder.match_service.cache),
        "query_cache_size": len(retriever.query_cache),
        "rss_mb": rss_mb(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark SNAPP matcher and basket performance.")
    parser.add_argument("--recipes", type=int, nargs="*", default=[1, 10, 60])
    parser.add_argument("--skip-cold", action="store_true")
    args = parser.parse_args()

    output: list[dict[str, object]] = []
    if not args.skip_cold:
        started = time.perf_counter()
        state = warmup_matcher(force=True)
        output.append(
            {
                "label": "cold_start_to_readiness",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "warmup_state": state.safe_dict(),
                "rss_mb": rss_mb(),
            }
        )
    elif warmup_status().status not in {"ready", "degraded"}:
        warmup_matcher()

    builder = BasketBuilder()
    for count in args.recipes:
        output.append(run_basket(builder, load_recipes(count), f"warm_uncached_{count}_recipes"))
    for count in args.recipes:
        output.append(run_basket(builder, load_recipes(count), f"warm_cached_{count}_recipes"))
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
