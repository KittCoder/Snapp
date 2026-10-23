#!/usr/bin/env python3
"""Read-only comparison profile using existing Render environment; never flushes Redis.

From Render's Model directory:
  python ../scripts/profile_store_catalog.py --samples 10 --all-stores --semantic
First request is process-cold; existing shared Redis entries are preserved.
All timing stages are inclusive/overlapping. SQL mode is NOT live Supabase.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'Model'), str(ROOT)]
from catalog_diagnostics import log_catalog_error
from catalog_timing import capture_timings, timing
from store_comparison import BasketComparison
from supabase_store_catalog import CandidateCache, DatabaseStoreRegistry, SupabaseGateway


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=10)
    parser.add_argument('--all-stores', action='store_true')
    parser.add_argument('--semantic', action='store_true', help='Use the existing MW semantic path')
    parser.add_argument('--sqlite', type=Path, help='Existing local SQL rehearsal; NOT Supabase')
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        parser.error('--samples must be between 1 and 100')
    engine = None
    try:
        if args.sqlite:
            from scripts.verify_store_catalog import SQLiteGateway
            gateway = SQLiteGateway(args.sqlite)
        else:
            gateway = SupabaseGateway()
        cache = CandidateCache()
        with capture_timings() as trace:
            start = time.perf_counter()
            engine = BasketComparison(DatabaseStoreRegistry(gateway, cache))
            registry_ms = (time.perf_counter() - start) * 1000
        print(json.dumps({'environment': 'local SQLite (NOT Supabase)' if args.sqlite else 'Supabase',
                          'registry_ms': round(registry_ms, 3), 'database_requests': gateway.query_count,
                          'stages': trace.summary(), 'semantic_requested': args.semantic,
                          'redis_policy': 'existing entries preserved; no flush'}))
        base = {'id': 'catalog-latency-profile', 'ingredients': ['8 oz rice', '2 oz butter']}
        ids = ['ctown:PS41_311', 'morton-williams']

        def run(label, recipes, stores):
            q0, h0, m0 = gateway.query_count, cache.hits, cache.misses
            with capture_timings() as trace:
                start = time.perf_counter()
                result = engine.compare(recipes, stores, mw_semantic=args.semantic)
                with timing('response_serialization'):
                    json.dumps(result, allow_nan=False)
                elapsed = (time.perf_counter() - start) * 1000
            summary = {'scenario': label, 'wall_ms': round(elapsed, 3),
                       'database_requests': gateway.query_count - q0,
                       'candidate_cache_hits': cache.hits - h0, 'candidate_cache_misses': cache.misses - m0,
                       'basket_cache_hit': result['cache_hit'], 'stages': trace.summary(),
                       'stores': [{'id': s['id'], 'reported_basket_latency_ms': s['latency_ms'],
                                   'complete': s['complete'], 'basket_total': s['basket_total'],
                                   'products': [p['product_name'] for p in s['product_selections']],
                                   'unknown_cost_items': s['unknown_cost_items']} for s in result['stores']]}
            # Never serialize environment values, provider responses or headers.
            print(json.dumps(summary), flush=True)
            return elapsed

        run('first_process_request', [base], ids)
        run('immediate_repeat', [base], ids)
        run('same_ingredients_different_store', [base], ['ctown:PU41_023'])
        run('same_stores_different_ingredient', [dict(base, ingredients=['8 oz rice', '2 oz cheddar cheese'])], ids)
        run('six_ingredient_basket', [{'id': 'multi-ingredient-profile', 'ingredients': [
            '8 oz rice', '2 oz butter', '8 oz cheddar cheese', '2 cloves garlic',
            '8 oz chickpeas', '1 tablespoon extra virgin olive oil']}], ids)
        groups = [('two', ids)]
        if args.all_stores:
            groups.append(('thirteen', list(engine.registry.stores)))
        for name, stores in groups:
            run(name + '_prewarm', [base], stores)
            for kind in ('basket_cached', 'candidate_cached'):
                times = []
                for index in range(args.samples):
                    recipes = [base] if kind == 'basket_cached' else [dict(base, id=name + '-sample-' + str(index))]
                    times.append(run(name + '_' + kind, recipes, stores))
                ordered = sorted(times)
                print(json.dumps({'benchmark': name + '_' + kind, 'samples': len(times),
                                  'p50_ms': round(statistics.median(times), 3),
                                  'p95_ms': round(ordered[max(0, (95 * len(times) + 99) // 100 - 1)], 3)}))
        return 0
    except Exception as exc:
        log_catalog_error(exc, 'catalog_latency_profile')
        return 1
    finally:
        if engine is not None:
            engine.pool.shutdown()


if __name__ == '__main__':
    sys.exit(main())
