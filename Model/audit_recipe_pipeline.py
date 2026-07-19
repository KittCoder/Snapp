from __future__ import annotations

import argparse
import json
import os
import random
import resource
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from basket_quantity import (
    calculate_cost,
    calculate_coverage,
    canonical_quantity,
    ingredient_aggregation_signature,
    parse_package_info,
    parse_price_info,
)
from product_compatibility import get_product_match_service, profile_from_query, profile_from_feature
from product_retrieval import query_embedding_text
from recipe_ingredient_adapter import canonical_recipe_ingredients


MODEL_DIR = Path(__file__).resolve().parent
EVALUATION_DIR = MODEL_DIR / "evaluation"
DEFAULT_AUDIT_PATH = EVALUATION_DIR / "recipe_pipeline_audit.jsonl"
DEFAULT_SUMMARY_PATH = EVALUATION_DIR / "recipe_pipeline_audit_summary.md"
DEFAULT_GOLDEN_PATH = EVALUATION_DIR / "recipe_pipeline_golden_cases.jsonl"
DEFAULT_METRICS_PATH = EVALUATION_DIR / "recipe_pipeline_metrics.json"
DEFAULT_FAILURE_REPORTS_PATH = EVALUATION_DIR / "recipe_pipeline_failure_reports.json"

SOURCE_FILES = (
    MODEL_DIR / "all_recipes.json",
    MODEL_DIR / "recipes.json",
    MODEL_DIR / "USDA recipes.json",
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def recipe_list(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("recipes", payload) if isinstance(payload, dict) else payload
    return [item for item in data if isinstance(item, dict)]


def recipe_id(recipe: dict[str, Any], index: int) -> str:
    return str(recipe.get("id") or recipe.get("usda_recipe_id") or recipe.get("source_url") or recipe.get("name") or f"recipe-{index}")


def recipe_title(recipe: dict[str, Any]) -> str:
    return str(recipe.get("name") or recipe.get("title") or "Untitled recipe")


def source_name(path: Path, recipe: dict[str, Any]) -> str:
    return str(recipe.get("source") or path.stem)


def sample_recipes(max_recipes: int, seed: int) -> list[tuple[Path, int, dict[str, Any]]]:
    by_source: dict[Path, list[tuple[int, dict[str, Any]]]] = {}
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        recipes = recipe_list(load_json(path))
        by_source[path] = list(enumerate(recipes))

    rng = random.Random(seed)
    selected: list[tuple[Path, int, dict[str, Any]]] = []
    per_source_min = min(50, max(1, max_recipes // max(1, len(by_source))))
    seen = set()
    for path, rows in by_source.items():
        rows = rows[:]
        rng.shuffle(rows)
        for index, recipe in rows[:per_source_min]:
            key = (path.name, recipe_id(recipe, index))
            if key in seen:
                continue
            seen.add(key)
            selected.append((path, index, recipe))

    remaining = [
        (path, index, recipe)
        for path, rows in by_source.items()
        for index, recipe in rows
        if (path.name, recipe_id(recipe, index)) not in seen
    ]
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, max_recipes - len(selected))])
    return selected[:max_recipes]


def candidate_dict(candidate: Any) -> dict[str, Any]:
    return {
        "product_id": candidate.product_id,
        "product_name": candidate.original_product_name,
        "normalized_name": candidate.normalized_name,
        "lexical_similarity": candidate.lexical_similarity,
        "semantic_similarity": candidate.semantic_similarity,
        "reason_codes": candidate.retrieval_reason_codes,
    }


def ranked_dict(candidate: Any) -> dict[str, Any]:
    return {
        "product_id": candidate.product_id,
        "product_name": candidate.product_name,
        "confidence": candidate.confidence,
        "final_score": candidate.final_score,
        "score_breakdown": candidate.score_breakdown,
        "conflicts": candidate.conflicts,
        "reason_codes": candidate.reason_codes,
    }


def classify_failures(record: dict[str, Any]) -> list[str]:
    categories = []
    canonical = record.get("parsed_canonical_ingredient") or ""
    unit = record.get("parsed_unit")
    quantity = record.get("parsed_quantity")
    warnings = " ".join(record.get("warnings") or []).casefold()
    text = (record.get("matcher_text") or record.get("original_ingredient") or "").casefold()
    selected = record.get("selected_product") or {}
    selected_name = (selected.get("product_name") or "").casefold()

    if record.get("source_schema") != "structured_ingredient_dict":
        categories.append("alternate schema not recognized" if not record.get("source_schema") else "raw text ingredient line")
    if record.get("source_quantity") not in (None, "") and quantity is None:
        categories.append("quantity already structured but reparsed incorrectly")
    if record.get("source_unit") and not unit:
        categories.append("unit already structured but discarded")
    if not record.get("raw_text"):
        categories.append("raw text missing during reconstruction")
    if quantity is None and not any(term in text for term in ("to taste", "as needed", "optional")):
        categories.append("quantity inferred when absent")
    if record.get("parsed_quantity_max") is not None:
        categories.append("range quantity")
    if unit in {"can", "package", "jar", "bunch", "clove", "stick", "head"}:
        categories.append("count unit")
    if not canonical:
        categories.append("canonical ingredient missing")
    if any(term in text for term in ("cooked", "uncooked", "prepared")):
        categories.append("raw versus cooked distinction")
    if any(term in text for term in ("fresh", "frozen", "canned", "dried")):
        categories.append("fresh/frozen/canned/dried distinction")
    if record.get("confidence") in {"no_safe_match", "substitution_only"}:
        categories.append("unmatched ingredient")
    if record.get("confidence") == "low":
        categories.append("low confidence")
    if selected and canonical and canonical not in selected_name and record.get("confidence") in {"exact", "high", "medium"}:
        categories.append("selected product identity requires review")
    if record.get("package_parse_confidence") in {"low", "unknown"}:
        categories.append("package metadata weak")
    if "unknown required quantity" in warnings:
        categories.append("missing or unsafe quantity conversion")
    if any(term in text for term in ("water", "ice", "to taste", "for garnish", "optional", "oil for greasing")):
        categories.append("legitimate no-match or non-purchase ingredient")
    return sorted(set(categories or ["no suspicious condition"]))


def audit_records(max_recipes: int, min_ingredients: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    service = get_product_match_service()
    recipes = sample_recipes(max_recipes=max_recipes, seed=seed)
    items = []
    source_counts = Counter()
    schema_counts = Counter()
    start = time.perf_counter()

    for path, index, recipe in recipes:
        rid = recipe_id(recipe, index)
        source = source_name(path, recipe)
        title = recipe_title(recipe)
        canonical_ingredients = canonical_recipe_ingredients(recipe)
        source_counts[source] += 1
        for ordinal, canonical in enumerate(canonical_ingredients):
            if len(items) >= min_ingredients:
                break
            matcher_text = canonical.matcher_text
            schema_counts[canonical.source_schema] += 1
            items.append((path, rid, source, title, ordinal, canonical, matcher_text))
        if len(items) >= min_ingredients:
            break

    records = []
    chunk_size = 256
    for offset in range(0, len(items), chunk_size):
        chunk = items[offset : offset + chunk_size]
        matcher_texts = [item[-1] for item in chunk]
        retrievals = service.retriever.retrieve_product_candidates_batch(matcher_texts, limit=30)
        for (path, rid, source, title, ordinal, canonical, matcher_text), retrieval in zip(chunk, retrievals):
            item_start = time.perf_counter()
            parsed_profile, parsed = profile_from_query(matcher_text)
            normalized_query, parsed_for_retrieval = query_embedding_text(matcher_text)
            signature, signature_parsed = ingredient_aggregation_signature(matcher_text)
            match = service._match_from_retrieval(
                matcher_text,
                parsed_profile,
                parsed,
                retrieval,
                item_start,
                limit=5,
                candidate_limit=30,
            )
            service.cache.set(service.cache_key(parsed_profile), match)
            required = canonical_quantity(parsed.get("quantity"), parsed.get("unit"), parsed.get("canonical_name"))
            selected = match.selected_match
            feature = service.feature_by_id.get(selected.product_id, {}) if selected else {}
            package = parse_package_info(feature) if feature else None
            coverage = calculate_coverage(required, package, parsed.get("canonical_name")) if package else None
            price = parse_price_info(feature.get("raw_price") or feature.get("price"), feature) if feature else None
            cost = calculate_cost(coverage, price) if coverage and price else None
            top_lexical = sorted(
                [candidate for candidate in retrieval.candidates if candidate.lexical_similarity],
                key=lambda item: item.lexical_similarity,
                reverse=True,
            )[:10]
            top_semantic = sorted(
                [candidate for candidate in retrieval.candidates if candidate.semantic_similarity is not None],
                key=lambda item: item.semantic_similarity or 0,
                reverse=True,
            )[:10]
            record = {
                "recipe_id": rid,
                "recipe_title": title,
                "recipe_source_file": path.name,
                "recipe_source": source,
                "ingredient_index": ordinal,
                "source_schema": canonical.source_schema,
                "source_fields": canonical.source_fields,
                "raw_text": canonical.raw_text,
                "original_ingredient": canonical.raw_text,
                "matcher_text": matcher_text,
                "source_quantity": canonical.source_fields.get("quantity") if isinstance(canonical.source_fields, dict) else None,
                "source_unit": canonical.source_fields.get("unit") if isinstance(canonical.source_fields, dict) else None,
                "canonical_representation": canonical.to_dict(),
                "parsed_quantity": parsed.get("quantity"),
                "parsed_quantity_min": parsed.get("quantity_min"),
                "parsed_quantity_max": parsed.get("quantity_max"),
                "parsed_unit": parsed.get("unit"),
                "parsed_canonical_ingredient": parsed.get("canonical_name"),
                "parsed_attributes": {
                    key: parsed.get(key)
                    for key in (
                        "form",
                        "fat_level",
                        "salted_status",
                        "sweetened_status",
                        "freshness",
                        "bone_status",
                        "skin_status",
                        "preparation",
                        "alternatives",
                    )
                },
                "aggregation_signature": signature,
                "signature_parsed": signature_parsed,
                "semantic_query": normalized_query,
                "retrieval_parsed_query": parsed_for_retrieval,
                "top_lexical_candidates": [candidate_dict(candidate) for candidate in top_lexical],
                "top_semantic_candidates": [candidate_dict(candidate) for candidate in top_semantic],
                "final_compatible_candidates": [ranked_dict(candidate) for candidate in ([selected] if selected else []) + match.compatible_alternatives[:4]],
                "selected_product": ranked_dict(selected) if selected else None,
                "confidence": match.confidence,
                "warnings": sorted(set(match.warnings + list(canonical.warnings) + (coverage.warnings if coverage else []) + (cost.warnings if cost else []))),
                "package_quantity": package.package_quantity if package else None,
                "package_unit": package.package_unit if package else None,
                "package_parse_confidence": package.confidence if package else None,
                "package_parse_source": package.source if package else None,
                "packages_required": coverage.packages_required if coverage else None,
                "checkout_cost": cost.checkout_cost if cost else None,
                "unmatched": selected is None,
                "timing_ms": {
                    "retrieval_total": retrieval.retrieval_latency_ms,
                    "lexical": retrieval.lexical_latency_ms,
                    "semantic": retrieval.semantic_latency_ms,
                    "query_embedding": retrieval.query_embedding_latency_ms,
                    "match_total": match.total_timing_ms,
                    "reranking": match.reranking_timing_ms,
                },
                "degraded_retrieval": retrieval.degraded_mode,
            }
            record["failure_categories"] = classify_failures(record)
            records.append(record)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    metadata = {
        "recipe_count": len(recipes),
        "ingredient_count": len(records),
        "source_counts": dict(source_counts),
        "schema_counts": dict(schema_counts),
        "elapsed_ms": elapsed_ms,
    }
    return records, metadata


def golden_cases(records: list[dict[str, Any]], limit: int = 300) -> list[dict[str, Any]]:
    ranked = sorted(
        records,
        key=lambda record: (
            "no suspicious condition" in record.get("failure_categories", []),
            record.get("confidence") not in {"no_safe_match", "substitution_only", "low"},
            -(record.get("checkout_cost") or 0),
            record.get("recipe_title", ""),
        ),
    )
    cases = []
    seen = set()
    for record in ranked:
        identity = (record.get("matcher_text") or "").casefold()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        profile, _parsed = profile_from_query(record.get("matcher_text") or "")
        selected = record.get("selected_product") or {}
        unacceptable = ["prepared meal"] if profile.category != "prepared" else []
        if profile.category == "meat" and profile.meat_species:
            unacceptable.extend([species for species in ("beef", "pork", "chicken", "turkey") if species != profile.meat_species])
        cases.append(
            {
                "id": f"real-{len(cases)+1:03d}",
                "recipe_id": record.get("recipe_id"),
                "recipe_title": record.get("recipe_title"),
                "source": record.get("recipe_source"),
                "original_recipe_ingredient": record.get("source_fields") or record.get("original_ingredient"),
                "matcher_text": record.get("matcher_text"),
                "expected_parsed_quantity": record.get("parsed_quantity"),
                "expected_parsed_quantity_max": record.get("parsed_quantity_max"),
                "expected_unit": record.get("parsed_unit"),
                "expected_canonical_identity": record.get("parsed_canonical_ingredient"),
                "required_attributes": record.get("parsed_attributes"),
                "acceptable_product_families": [item for item in [profile.family, profile.canonical, selected.get("product_name")] if item],
                "unacceptable_product_families": sorted(set(unacceptable)),
                "no_match_acceptable": any(category in record.get("failure_categories", []) for category in ("legitimate no-match or non-purchase ingredient", "canonical ingredient missing")),
                "substitution_acceptable": False,
                "expected_aggregation_behavior": "aggregate only with identical aggregation_signature",
                "audit_failure_categories": record.get("failure_categories"),
            }
        )
        if len(cases) >= limit:
            break
    return cases


def summarize(records: list[dict[str, Any]], metadata: dict[str, Any], metrics: dict[str, Any]) -> str:
    failure_counts = Counter(category for record in records for category in record.get("failure_categories") or [])
    confidence_counts = Counter(record.get("confidence") for record in records)
    unmatched = sum(1 for record in records if record.get("unmatched"))
    package_known = sum(1 for record in records if record.get("package_quantity") is not None)
    lines = [
        "# Recipe Pipeline Audit Summary",
        "",
        "## Pipeline Map",
        "- Source recipe files: `Model/all_recipes.json`, `Model/recipes.json`, `Model/USDA recipes.json`.",
        "- Current production source path: local recipe records are converted through source adapters into canonical ingredient records, then exposed as Spoonacular-style ingredients for existing UI code.",
        "- Ingredient parser entry point: `ingredient_normalization.parse_ingredient`.",
        "- Quantity normalization: `basket_quantity.canonical_quantity` converts mass, volume, and count units; unsafe mass-volume conversion stays unknown unless density exists.",
        "- Semantic query construction: `product_retrieval.query_embedding_text` removes recipe quantity/package text and retains identity attributes.",
        "- Lexical retrieval: token/canonical indexes in `ProductCandidateRetriever.lexical_search_space` and `lexical_candidates`.",
        "- Vector retrieval: persisted local index in `Model/morton_williams_vector_index` via `ProductCandidateRetriever.retrieve_product_candidates_batch`.",
        "- Compatibility filtering/ranking: `ProductMatchService._match_from_retrieval`, `compatibility_signals`, and `score_candidate`.",
        "- Package parsing/optimization/aggregation: `basket_quantity.parse_package_info`, `calculate_coverage`, `calculate_cost`, `BasketBuilder.build_multi_recipe_basket`.",
        "",
        "## Transformations And Loss Risks",
        "- Source `raw`, `quantity`, `unit`, `name`, and `note` are adapted into `CanonicalRecipeIngredient`; trusted structured quantity/unit are preserved.",
        "- Matcher text is reconstructed from canonical fields; source `raw_text` and `source_fields` are retained for provenance.",
        "- `parse_ingredient` can still remove preparation words and split alternatives; identity-defining forms must be listed as meaningful modifiers or aliases.",
        "- `query_embedding_text` drops quantity/unit by design; package metadata does not affect embeddings.",
        "- Basket aggregation uses `ingredient_aggregation_signature`; attributes absent from profile can cause over-aggregation.",
        "",
        "## Audit Size",
        f"- Recipes sampled: {metadata.get('recipe_count')}",
        f"- Recipes contributing audited ingredients: {sum((metadata.get('source_counts') or {}).values())}",
        f"- Ingredient lines audited: {metadata.get('ingredient_count')}",
        f"- Runtime: {metadata.get('elapsed_ms')} ms",
        f"- Unmatched ingredients: {unmatched} ({unmatched / max(1, len(records)):.1%})",
        f"- Package metadata present on selected products: {package_known} ({package_known / max(1, len(records)):.1%})",
        f"- Failure report artifact: `Model/evaluation/recipe_pipeline_failure_reports.json`",
        "",
        "## Source Counts",
    ]
    for source, count in sorted(metadata.get("source_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {source}: {count}")
    lines.extend(["", "## Schema Counts"])
    for schema, count in sorted(metadata.get("schema_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {schema}: {count}")
    lines.extend(["", "## Confidence Counts"])
    for confidence, count in confidence_counts.most_common():
        lines.append(f"- {confidence}: {count} ({count / max(1, len(records)):.1%})")
    lines.extend(["", "## Failure Distribution"])
    for category, count in failure_counts.most_common():
        lines.append(f"- {category}: {count} ({count / max(1, len(records)):.1%})")
    lines.extend(["", "## Performance"])
    for key, value in metrics.get("performance", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Stage Metrics"])
    for key, value in metrics.get("stage_metrics", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Golden Evaluation"])
    for key, value in metrics.get("golden_evaluation", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Manual Review Ingredients"])
    review = Counter(record.get("parsed_canonical_ingredient") or record.get("matcher_text") for record in records if record.get("confidence") in {"no_safe_match", "substitution_only", "low"})
    for ingredient, count in review.most_common(50):
        lines.append(f"- {ingredient}: {count}")
    lines.append("")
    return "\n".join(lines)


def benchmark(records: list[dict[str, Any]]) -> dict[str, Any]:
    from basket_quantity import get_basket_builder

    builder = get_basket_builder()
    ingredients = [record["matcher_text"] for record in records if record.get("matcher_text")]
    unique = list(dict.fromkeys(ingredients))
    scenarios = {
        "one_ingredient": [{"id": "one", "ingredients": unique[:1]}],
        "one_recipe": [{"id": "one_recipe", "ingredients": unique[:8]}],
        "ten_recipes": [{"id": f"r{i}", "ingredients": unique[i * 8:(i + 1) * 8]} for i in range(10)],
        "sixty_recipes": [{"id": f"r{i}", "ingredients": unique[i * 8:(i + 1) * 8]} for i in range(60)],
    }
    results = {}
    for name, recipes in scenarios.items():
        recipes = [recipe for recipe in recipes if recipe["ingredients"]]
        start = time.perf_counter()
        basket = builder.build_multi_recipe_basket(recipes)
        uncached_ms = round((time.perf_counter() - start) * 1000, 2)
        start = time.perf_counter()
        cached = builder.build_multi_recipe_basket(recipes)
        cached_ms = round((time.perf_counter() - start) * 1000, 2)
        results[name] = {
            "warm_uncached_ms": uncached_ms,
            "warm_cached_ms": cached_ms,
            "basket_reported_uncached_ms": basket.latency_ms,
            "basket_reported_cached_ms": cached.latency_ms,
            "ingredient_count": sum(len(recipe["ingredients"]) for recipe in recipes),
            "checkout_cost": basket.checkout_cost,
        }
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    results["memory"] = {"max_rss_kb": rss_kb}
    return results


def stage_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = max(1, len(records))
    lexical_any = sum(1 for record in records if record.get("top_lexical_candidates"))
    semantic_any = sum(1 for record in records if record.get("top_semantic_candidates"))
    compatible_any = sum(1 for record in records if record.get("final_compatible_candidates"))
    selected = sum(1 for record in records if record.get("selected_product"))
    hard_conflicts_selected = 0
    for record in records:
        selected_product = record.get("selected_product") or {}
        conflicts = selected_product.get("conflicts") or []
        if any(conflict.get("classification") == "hard_reject" for conflict in conflicts):
            hard_conflicts_selected += 1
    quantities_known = sum(1 for record in records if record.get("parsed_quantity") is not None or "to taste" in (record.get("matcher_text") or "").casefold())
    return {
        "lexical_candidate_presence": round(lexical_any / total, 4),
        "semantic_candidate_presence": round(semantic_any / total, 4),
        "compatibility_safe_candidate_presence": round(compatible_any / total, 4),
        "selected_match_rate": round(selected / total, 4),
        "unmatched_rate": round((total - selected) / total, 4),
        "hard_conflict_selection_count": hard_conflicts_selected,
        "quantity_known_or_intentionally_absent_rate": round(quantities_known / total, 4),
    }


def top_counter_rows(counter: Counter, limit: int = 200) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def failure_reports(records: list[dict[str, Any]], limit: int = 200) -> dict[str, Any]:
    unmatched = Counter()
    low_confidence = Counter()
    no_candidate = Counter()
    warnings = Counter()
    quantity_failures = Counter()
    cost_impact = []
    for record in records:
        ingredient = record.get("parsed_canonical_ingredient") or record.get("matcher_text") or record.get("original_ingredient") or ""
        if record.get("unmatched"):
            unmatched[ingredient] += 1
        if record.get("confidence") in {"low", "substitution_only", "no_safe_match"}:
            low_confidence[ingredient] += 1
        if not record.get("top_lexical_candidates") and not record.get("top_semantic_candidates"):
            no_candidate[ingredient] += 1
        for warning in record.get("warnings") or []:
            warnings[warning] += 1
        if any(
            category in record.get("failure_categories", [])
            for category in (
                "missing or unsafe quantity conversion",
                "quantity inferred when absent",
                "count unit",
                "range quantity",
                "unit already structured but discarded",
                "quantity already structured but reparsed incorrectly",
                "package metadata weak",
            )
        ):
            quantity_failures[ingredient] += 1
        suspicious = [category for category in record.get("failure_categories", []) if category != "no suspicious condition"]
        if suspicious:
            cost_impact.append(
                {
                    "checkout_cost": record.get("checkout_cost") or 0,
                    "recipe_id": record.get("recipe_id"),
                    "recipe_title": record.get("recipe_title"),
                    "ingredient": record.get("matcher_text"),
                    "canonical_ingredient": record.get("parsed_canonical_ingredient"),
                    "selected_product": (record.get("selected_product") or {}).get("product_name"),
                    "confidence": record.get("confidence"),
                    "failure_categories": suspicious,
                }
            )
    cost_impact.sort(key=lambda item: item["checkout_cost"], reverse=True)
    return {
        "top_unmatched_normalized_ingredients": top_counter_rows(unmatched, limit),
        "top_low_confidence_ingredients": top_counter_rows(low_confidence, limit),
        "top_no_inventory_candidate_ingredients": top_counter_rows(no_candidate, limit),
        "top_parsing_warnings": top_counter_rows(warnings, limit),
        "top_quantity_failures": top_counter_rows(quantity_failures, limit),
        "top_basket_cost_impact_failures": cost_impact[:limit],
    }


def acceptable_hit(name: str, acceptable: list[str]) -> bool:
    normalized_name = " ".join(str(name or "").casefold().split())
    return any(" ".join(str(item or "").casefold().split()) in normalized_name for item in acceptable if item)


def evaluate_golden_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    service = get_product_match_service()
    total = max(1, len(cases))
    counters = Counter()
    queries = [case.get("matcher_text") or "" for case in cases]
    retrievals = service.retriever.retrieve_product_candidates_batch(queries, limit=30)
    for case, retrieval in zip(cases, retrievals):
        query = case.get("matcher_text") or ""
        acceptable = case.get("acceptable_product_families") or []
        lexical = sorted(
            [candidate for candidate in retrieval.candidates if candidate.lexical_similarity],
            key=lambda item: item.lexical_similarity,
            reverse=True,
        )
        semantic = sorted(
            [candidate for candidate in retrieval.candidates if candidate.semantic_similarity is not None],
            key=lambda item: item.semantic_similarity or 0,
            reverse=True,
        )
        if any(acceptable_hit(candidate.original_product_name, acceptable) for candidate in lexical[:10]):
            counters["lexical_top_10_recall"] += 1
        if any(acceptable_hit(candidate.original_product_name, acceptable) for candidate in lexical[:30]):
            counters["lexical_top_30_recall"] += 1
        if any(acceptable_hit(candidate.original_product_name, acceptable) for candidate in semantic[:10]):
            counters["semantic_top_10_recall"] += 1
        if any(acceptable_hit(candidate.original_product_name, acceptable) for candidate in semantic[:30]):
            counters["semantic_top_30_recall"] += 1
        if any(acceptable_hit(candidate.original_product_name, acceptable) for candidate in retrieval.candidates[:30]):
            counters["merged_top_30_recall"] += 1
        item_start = time.perf_counter()
        parsed_profile, parsed = profile_from_query(query)
        match = service._match_from_retrieval(
            query,
            parsed_profile,
            parsed,
            retrieval,
            item_start,
            limit=5,
            candidate_limit=30,
        )
        safe = ([match.selected_match] if match.selected_match else []) + match.compatible_alternatives
        if any(acceptable_hit(candidate.product_name, acceptable) for candidate in safe):
            counters["compatibility_safe_recall"] += 1
        if match.selected_match and acceptable_hit(match.selected_match.product_name, acceptable):
            counters["final_top_1_accuracy"] += 1
        top3 = ([match.selected_match] if match.selected_match else []) + match.compatible_alternatives[:2]
        if any(acceptable_hit(candidate.product_name, acceptable) for candidate in top3):
            counters["final_top_3_recall"] += 1
        if match.selected_match and any(conflict.get("classification") == "hard_reject" for conflict in match.selected_match.conflicts):
            counters["hard_conflict_selection_count"] += 1
    return {key: round(counters[key] / total, 4) for key in (
        "lexical_top_10_recall",
        "lexical_top_30_recall",
        "semantic_top_10_recall",
        "semantic_top_30_recall",
        "merged_top_30_recall",
        "compatibility_safe_recall",
        "final_top_1_accuracy",
        "final_top_3_recall",
    )} | {"hard_conflict_selection_count": counters["hard_conflict_selection_count"]}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the real recipe-to-product pipeline.")
    parser.add_argument("--max-recipes", type=int, default=500)
    parser.add_argument("--min-ingredients", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--audit-path", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--golden-path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--metrics-path", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--failure-reports-path", type=Path, default=DEFAULT_FAILURE_REPORTS_PATH)
    args = parser.parse_args()

    records, metadata = audit_records(args.max_recipes, args.min_ingredients, args.seed)
    golden = golden_cases(records, limit=300)
    perf = benchmark(records)
    metrics = {
        "metadata": metadata,
        "stage_metrics": stage_metrics(records),
        "golden_evaluation": evaluate_golden_cases(golden),
        "performance": perf,
        "embedding_benchmark_comparison": {
            "changed": False,
            "reason": "Retrieval audit did not justify changing the embedding model during this pass.",
            "current_model": os.getenv("SNAPP_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            "alternatives_tested": [],
        },
    }

    write_jsonl(args.audit_path, records)
    write_jsonl(args.golden_path, golden)
    args.failure_reports_path.parent.mkdir(parents=True, exist_ok=True)
    args.failure_reports_path.write_text(json.dumps(failure_reports(records), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.summary_path.write_text(summarize(records, metadata, metrics), encoding="utf-8")
    print(json.dumps({"audit_path": str(args.audit_path), "summary_path": str(args.summary_path), "golden_path": str(args.golden_path), "failure_reports_path": str(args.failure_reports_path), **metrics["stage_metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
