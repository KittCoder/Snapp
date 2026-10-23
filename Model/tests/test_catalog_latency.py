"""Cache reuse must preserve selection, version safety, isolation and unknown costs."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_timing import capture_timings
from product_ontology import describe
from store_catalogs import CatalogError, ROOT
from store_comparison import BasketComparison
from supabase_store_catalog import (CandidateCache, DatabaseStoreCatalog, DatabaseStoreRegistry,
                                    FEATURE_VERSION, PreparedCatalogCache, SupabaseGateway)
from test_product_compatibility import feature
from test_supabase_store_catalog import Cache


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in ('elapsed_ms', 'latency_ms', 'cache_hit')}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


class Gateway:
    def __init__(self):
        manifest = json.loads((ROOT / 'Model/store_catalog_manifest.json').read_text())
        self.entries = [{'id': m['id'], 'metadata': m} for m in manifest]
        self.versions = [{'id': 'version-' + m['id'], 'store_id': m['id'],
                          'source_version': m['inventory_version'], 'product_count': m['product_count'],
                          'feature_version': FEATURE_VERSION} for m in manifest]
        self.selects = []
        self.lookups = []
        self.price = '$4.00'

    def select(self, table, params):
        self.selects.append((table, copy.deepcopy(params)))
        rows = self.entries if table == 'stores' else self.versions
        if 'store_id' in params:
            rows = [v for v in rows if 'eq.' + v['store_id'] == params['store_id']]
        return copy.deepcopy(rows)

    def candidates(self, store, version, field, values, limit):
        self.lookups.append((store, version, field, values))
        entry = next(e['metadata'] for e in self.entries if e['id'] == store)
        rows = []
        for pos, name in enumerate(('Long Grain Rice', 'Butter')):
            f = feature(store + '-' + str(pos), name)
            f.update(raw_price=self.price, package_size='16 oz', price=float(self.price[1:]))
            identity = describe(name, feature=f, product=True)
            if field != 'normalized_name' and getattr(identity, field) not in values:
                continue
            source = {'retailer': entry['retailer'], 'store_id': entry['store_id'],
                      'source_url': 'https://example.test/product', 'availability': True}
            rows.append({'feature_json': f, 'identity_json': asdict(identity),
                         'source_json': source, 'source_position': pos})
        return rows


class CatalogLatencyTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Gateway()
        self.cache = CandidateCache(Cache())
        self.registry = DatabaseStoreRegistry(self.gateway, self.cache)
        self.engine = BasketComparison(self.registry)
        self.addCleanup(self.engine.pool.shutdown)
        self.ids = ['ctown:PS41_311', 'ctown:PU41_023']
        self.recipes = [{'id': 'latency-regression', 'ingredients': ['8 oz rice', '2 oz butter']}]

    def test_one_fresh_active_version_read_for_thirteen_stores_even_on_result_hit(self):
        ids = list(self.registry.stores)
        self.engine.compare(self.recipes, ids)
        self.gateway.selects.clear()
        result = self.engine.compare(self.recipes, ids)
        self.assertTrue(result['cache_hit'])
        self.assertEqual(len(self.gateway.selects), 1)
        self.assertEqual(self.gateway.selects[0][0], 'store_inventory_versions')
        self.assertEqual(self.gateway.selects[0][1]['active'], 'eq.true')

    def test_candidate_cache_hit_and_prepared_reuse_preserve_uncached_result(self):
        first = self.engine.compare(self.recipes, self.ids)
        queries = len(self.gateway.lookups)
        prepared = next(v[0] for k, v in self.registry.prepared_cache.values.items() if k[0] == self.ids[0])
        self.engine.cache.clear()
        second = self.engine.compare(self.recipes, self.ids)
        self.assertFalse(second['cache_hit'])
        self.assertEqual(len(self.gateway.lookups), queries)
        self.assertGreaterEqual(self.cache.hits, 4)
        self.assertIs(next(v[0] for k, v in self.registry.prepared_cache.values.items() if k[0] == self.ids[0]), prepared)
        self.assertEqual(stable(first), stable(second))
        # Reused builder never grows an unbounded cache of prior user recipes.
        self.engine.cache.clear()
        self.engine.compare([dict(self.recipes[0], id='different-recipe')], self.ids)
        self.assertEqual(len(prepared.builder()._basket_cache), 1)

    def test_inventory_activation_rejects_cached_basket_and_new_catalog_misses_old_candidates(self):
        self.engine.compare(self.recipes, self.ids)
        version = next(v for v in self.gateway.versions if v['store_id'] == self.ids[0])
        version['id'] = 'new-active-version'
        with self.assertRaises(CatalogError):
            self.engine.compare(self.recipes, self.ids)
        old = self.registry.stores[self.ids[0]]
        self.registry.stores[self.ids[0]] = DatabaseStoreCatalog(
            old.metadata, version['id'], self.gateway, self.cache, self.registry.prepared_cache)
        self.gateway.price = '$9.00'
        result = self.engine.compare(self.recipes, self.ids)
        self.assertFalse(result['cache_hit'])
        self.assertTrue(any(q[1] == version['id'] for q in self.gateway.lookups))
        selected = next(s for s in result['stores'] if s['id'] == self.ids[0])
        self.assertTrue(any(p['checkout_cost'] == 9 for p in selected['product_selections']))

    def test_feature_change_rejects_old_db_metadata_before_result_cache(self):
        self.engine.compare(self.recipes, self.ids)
        version = next(v for v in self.gateway.versions if v['store_id'] == self.ids[0])
        version['feature_version'] = 'stale'
        with self.assertRaises(CatalogError):
            self.engine.compare(self.recipes, self.ids)

    def test_runtime_feature_change_invalidates_basket_candidate_and_prepared_caches(self):
        self.engine.compare(self.recipes, self.ids)
        previous = list(self.registry.prepared_cache.values.values())[0][0]
        count = len(self.gateway.lookups)
        with patch('supabase_store_catalog.FEATURE_VERSION', 'next-feature-version'):
            for v in self.gateway.versions:
                v['feature_version'] = 'next-feature-version'
            result = self.engine.compare(self.recipes, self.ids)
        self.assertFalse(result['cache_hit'])
        self.assertGreater(len(self.gateway.lookups), count)
        self.assertTrue(any(k[0] == self.ids[0] and k[2] == 'next-feature-version'
                            and v[0] is not previous for k, v in self.registry.prepared_cache.values.items()))

    def test_quantity_change_reuses_candidate_cache_but_not_old_basket(self):
        catalog = self.registry.stores[self.ids[0]]
        catalog.request_catalog([{'ingredients': ['8 oz rice']}])
        count = len(self.gateway.lookups)
        catalog.request_catalog([{'ingredients': ['16 oz rice']}])
        self.assertEqual(len(self.gateway.lookups), count)
        self.assertGreater(self.cache.hits, 0)
        first = self.engine.compare([{'ingredients': ['8 oz rice']}], [self.ids[0]])
        second = self.engine.compare([{'ingredients': ['32 oz rice']}], [self.ids[0]])
        self.assertEqual(first['stores'][0]['product_selections'][0]['checkout_cost'], 4)
        self.assertEqual(second['stores'][0]['product_selections'][0]['checkout_cost'], 8)
        self.assertFalse(second['cache_hit'])
        self.assertEqual(len(self.gateway.lookups), count)

    def test_same_family_queries_share_one_bounded_pool_within_basket(self):
        catalog = self.registry.stores[self.ids[0]]
        catalog.request_catalog([{'ingredients': ['8 oz white rice', '8 oz brown rice']}])
        self.assertEqual(len(self.gateway.lookups), 1)
        self.assertEqual(self.gateway.lookups[0][2], 'family')

    def test_store_order_does_not_fragment_basket_cache(self):
        expected = self.engine.compare(self.recipes, self.ids)
        actual = self.engine.compare(self.recipes, list(reversed(self.ids)))
        self.assertTrue(actual['cache_hit'])
        self.assertEqual(stable(expected), stable(actual))

    def test_store_isolation_after_prepared_and_candidate_cache_hits(self):
        for _ in range(2):
            result = self.engine.compare(self.recipes, self.ids)
            for store in result['stores']:
                self.assertTrue(all(p['product_id'].startswith(store['id'] + '-')
                                    for p in store['product_selections']))
            self.engine.cache.clear()

    def test_redis_unavailable_uses_database_and_same_result(self):
        expected = self.engine.compare(self.recipes, self.ids)
        client = Mock()
        client.get.side_effect = OSError('connection unavailable')
        client.setex.side_effect = OSError('connection unavailable')
        fresh = BasketComparison(DatabaseStoreRegistry(self.gateway, CandidateCache(client)))
        self.addCleanup(fresh.pool.shutdown)
        self.assertEqual(stable(expected), stable(fresh.compare(self.recipes, self.ids)))

    def test_duplicate_or_missing_active_version_fails_closed(self):
        self.engine.compare(self.recipes, self.ids)
        original = copy.deepcopy(self.gateway.versions)
        target = next(v for v in original if v['store_id'] == self.ids[0])
        for versions in ([v for v in original if v['store_id'] != self.ids[0]], original + [target]):
            self.gateway.versions = versions
            with self.assertRaises(CatalogError):
                self.engine.compare(self.recipes, self.ids)

    def test_prepared_cache_is_bounded_and_changed_row_bytes_do_not_reuse_state(self):
        cache = PreparedCatalogCache(max_rows=3, max_entries=2)
        a, b = object(), object()
        cache.put('a', a, 2)
        cache.put('b', b, 2)
        self.assertIsNone(cache.get('a'))
        self.assertIs(cache.get('b'), b)
        cache.put('oversize', a, 4)
        self.assertIsNone(cache.get('oversize'))
        self.assertLessEqual(cache.rows, 3)
        catalog = self.registry.stores[self.ids[0]]
        first = catalog.request_catalog(self.recipes)
        # Same version/IDs, modified cache bytes: parsed profiles cannot be reused.
        for key, value in self.cache.client.values.items():
            rows = json.loads(value)
            for row in rows:
                row['feature_json']['raw_price'] = '$12.00'
            self.cache.client.values[key] = json.dumps(rows)
        self.assertIsNot(first, catalog.request_catalog(self.recipes))

    def test_timing_trace_crosses_pool_boundary_without_ingredient_or_secret_values(self):
        with capture_timings() as trace:
            self.engine.compare(self.recipes, self.ids)
        stages = trace.summary()
        self.assertEqual({s['store_id'] for s in stages if s['stage'] == 'store_basket'}, set(self.ids))
        self.assertTrue(any(s['stage'] == 'active_inventory_versions' for s in stages))
        self.assertNotIn('8 oz rice', json.dumps(stages))


class GatewayConnectionTests(unittest.TestCase):
    def test_sequential_calls_reuse_session_without_redirects(self):
        response = Mock(status_code=200, content=b'[]')
        response.json.return_value = []
        with patch('supabase_store_catalog.requests.Session') as factory:
            factory.return_value.request.return_value = response
            gateway = SupabaseGateway('https://example.test', 'test-key')
            gateway.select('stores', {})
            gateway.select('store_inventory_versions', {})
            factory.assert_called_once()
            self.assertEqual(factory.return_value.request.call_count, 2)
            self.assertFalse(factory.return_value.request.call_args.kwargs['allow_redirects'])
