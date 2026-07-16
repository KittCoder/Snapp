import argparse
import json
import statistics
import time
from pathlib import Path

from product_compatibility import (
    DEFAULT_EVALUATION_FIXTURE,
    ProductMatchService,
)


def load_cases(path):
    cases = []
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def selected_text(result):
    if not result.selected_match:
        return ""
    return " ".join(
        str(value or "")
        for value in (
            result.selected_match.product_name,
            result.selected_match.normalized_name,
            result.selected_match.canonical_ingredient,
        )
    ).casefold()


def matches_any(text, patterns):
    return any(pattern.casefold() in text for pattern in patterns or [])


def confidence_value(value):
    order = {
        "no_safe_match": 0,
        "substitution_only": 1,
        "low": 2,
        "medium": 3,
        "high": 4,
        "exact": 5,
    }
    return order.get(value, 0)


def evaluate(cases, service):
    first_latencies = []
    cached_latencies = []
    correct_top1 = 0
    top3_recall = 0
    incompatible = 0
    hard_conflicts = 0
    no_safe_expected = 0
    no_safe_correct = 0
    substitutions = 0
    substitution_correct = 0
    confidence_by_correctness = {"correct": [], "incorrect": []}
    failures = []

    for case in cases:
        started = time.perf_counter()
        result = service.match_recipe_ingredient(case["query"], limit=5)
        first_latencies.append((time.perf_counter() - started) * 1000)
        cached_started = time.perf_counter()
        cached = service.match_recipe_ingredient(case["query"], limit=5)
        cached_latencies.append((time.perf_counter() - cached_started) * 1000)

        text = selected_text(result)
        unacceptable = matches_any(text, case.get("unacceptable_patterns"))
        acceptable = matches_any(text, case.get("acceptable_patterns"))
        if case.get("expect_no_safe_match"):
            no_safe_expected += 1
            if result.confidence == "no_safe_match":
                no_safe_correct += 1
        elif acceptable:
            correct_top1 += 1
        else:
            failures.append({"query": case["query"], "selected": text, "confidence": result.confidence})

        top3_text = " ".join(
            selected_text(type("R", (), {"selected_match": candidate})())
            for candidate in ([result.selected_match] if result.selected_match else []) + result.compatible_alternatives[:2]
            if candidate
        )
        if matches_any(top3_text, case.get("acceptable_patterns")):
            top3_recall += 1
        if unacceptable:
            incompatible += 1
        if result.selected_match and any(
            conflict.get("classification") == "hard_reject"
            for conflict in result.selected_match.conflicts
        ):
            hard_conflicts += 1
        if result.confidence == "substitution_only":
            substitutions += 1
            if case.get("substitutions_allowed"):
                substitution_correct += 1
        confidence_by_correctness["correct" if acceptable else "incorrect"].append(confidence_value(result.confidence))

    total = len(cases) or 1
    return {
        "case_count": len(cases),
        "top_1_compatible_accuracy": round(correct_top1 / total, 4),
        "top_3_compatible_recall": round(top3_recall / total, 4),
        "incompatible_match_rate": round(incompatible / total, 4),
        "hard_conflict_selection_count": hard_conflicts,
        "no_safe_match_precision": round(no_safe_correct / no_safe_expected, 4) if no_safe_expected else None,
        "substitution_precision": round(substitution_correct / substitutions, 4) if substitutions else None,
        "average_confidence_correct": round(statistics.mean(confidence_by_correctness["correct"]), 3)
        if confidence_by_correctness["correct"]
        else None,
        "average_confidence_incorrect": round(statistics.mean(confidence_by_correctness["incorrect"]), 3)
        if confidence_by_correctness["incorrect"]
        else None,
        "average_uncached_latency_ms": round(statistics.mean(first_latencies), 2) if first_latencies else 0,
        "average_cached_latency_ms": round(statistics.mean(cached_latencies), 2) if cached_latencies else 0,
        "cache_hit_rate_repeated_evaluation": round(sum(1 for latency in cached_latencies if latency < 5) / total, 4),
        "common_failure_categories": failures[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate product compatibility matching.")
    parser.add_argument("--fixture", default=str(DEFAULT_EVALUATION_FIXTURE))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    cases = load_cases(args.fixture)
    if args.limit:
        cases = cases[: args.limit]
    metrics = evaluate(cases, ProductMatchService())
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
