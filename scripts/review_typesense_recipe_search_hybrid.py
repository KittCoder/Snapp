#!/usr/bin/env python3
"""Paired retrieval comparison; no generation or external embedding client."""
import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Model'))
from recipe_search_typesense import (TypesenseConfig, search_recipes, ingredient_variants,
                                    EMBEDDING_MODEL, EMBEDDING_DIMENSION, typesense_request, dairy_ingredient_names)
from review_typesense_recipe_search import BENCHMARK_QUERIES

MODES = [('keyword', None), ('hybrid_0.3', .3), ('hybrid_0.5', .5), ('hybrid_0.7', .7)]


def audit(result):
    state = result['state']
    violations = []
    for recipe in result['results']:
        names = {x.lower() for x in recipe['ingredient_names']}
        reasons = []
        total = recipe['total_time_minutes']
        if state['max_time'] is not None and (total is None or total > state['max_time']): reasons.append('max_time')
        if state['min_time'] is not None and (total is None or total < state['min_time']): reasons.append('min_time')
        for term in state['include_ingredients']:
            if not names.intersection(ingredient_variants(term)): reasons.append('include:' + term)
        for term in state['exclude_ingredients']:
            if names.intersection(ingredient_variants(term)): reasons.append('exclude:' + term)
        for term in state['categories'] + state['dietary']:
            if term == 'dairy_free':
                if names.intersection(dairy_ingredient_names()): reasons.append('dairy_free')
            elif term not in recipe['categories']: reasons.append('category:' + term)
        if reasons: violations.append({'id': recipe['id'], 'reasons': reasons})
    return {'returned': len(result['results']), 'violations': violations,
            'status': 'no_results' if not result['results'] else ('pass' if not violations else 'fail')}


def summary(values):
    return {'median_ms': round(statistics.median(values), 2),
            'p95_ms': round(statistics.quantiles(values, n=20)[18], 2)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('typesense_recipe_search_hybrid_review.json'))
    parser.add_argument('--rounds', type=int, default=3)
    args = parser.parse_args()
    config = TypesenseConfig(timeout_seconds=30)
    collection = typesense_request(config, 'GET', '/collections/' + config.collection)
    version = typesense_request(config, 'GET', '/debug')['version']
    expected = sum(1 for line in Path('data/snapp_typesense_documents.jsonl').open() if line.strip())
    if collection['num_documents'] != expected:
        raise RuntimeError('Collection count differs from exported documents; finish indexing first')
    embedding = next(field for field in collection['fields'] if field['name'] == 'embedding')
    if embedding['num_dim'] != EMBEDDING_DIMENSION or embedding['embed']['model_config']['model_name'] != EMBEDDING_MODEL:
        raise RuntimeError('Unexpected embedding schema')
    results = {q: {} for q in BENCHMARK_QUERIES}
    samples = {mode: {key: [] for key in ('total_latency_ms', 'typesense_latency_ms', 'typesense_server_latency_ms')} for mode, _ in MODES}
    cold = {}
    for mode, alpha in MODES:
        result = search_recipes(BENCHMARK_QUERIES[0], config=config, mode='keyword' if alpha is None else 'hybrid', alpha=alpha or .5, allow_fallback=False)
        cold[mode] = result['total_latency_ms']
    for iteration in range(args.rounds):
        for i, query in enumerate(BENCHMARK_QUERIES):
            print(f"Round {iteration + 1}: {query}", flush=True)
            order = MODES[(i+iteration)%4:] + MODES[:(i+iteration)%4]
            for mode, alpha in order:
                result = search_recipes(query, config=config, mode='keyword' if alpha is None else 'hybrid', alpha=alpha or .5, allow_fallback=False)
                result['filter_audit'] = audit(result)
                # Filter strings contain expanded vocabulary, so avoid repeating them in the artifact.
                result.pop('filter_by')
                if iteration == 0: results[query][mode] = result
                for key in samples[mode]: samples[mode][key].append(result[key])
        print(f'Completed round {iteration + 1}/{args.rounds}', flush=True)
    previous = json.loads(Path('typesense_recipe_search_review.json').read_text())
    artifact = {'query_count': len(BENCHMARK_QUERIES), 'rounds': args.rounds,
                'typesense_version': version, 'documents_indexed': collection['num_documents'],
                'embedding_model': EMBEDDING_MODEL, 'embedding_dimension': EMBEDDING_DIMENSION,
                'method': 'Same 50 queries; shared parser, filters and dedup; rotated modes; warmup excluded; Typesense query cache not enabled. Strict hybrid: no fallback.',
                'historical_keyword_baseline': {k: previous.get(k) for k in ('median_latency_ms','p95_latency_ms')},
                'first_query_latency_ms': cold,
                'latency': {mode: {key: summary(values) for key, values in metrics.items()} for mode, metrics in samples.items()},
                'duplicate_removals_first_round': {mode: sum(results[q][mode]['duplicates_removed'] for q in results) for mode, _ in MODES},
                'queries': [{'query': q, 'modes': results[q]} for q in BENCHMARK_QUERIES],
                'latency_samples': samples}
    args.output.write_text(json.dumps(artifact, indent=2) + '\n')
    print(json.dumps(artifact['latency'], indent=2))


if __name__ == '__main__':
    main()
