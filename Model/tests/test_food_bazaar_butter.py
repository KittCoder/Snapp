"""Butter purchase identity and legacy Food Bazaar inventory replay."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from flask import Flask, jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import store_comparison_api
import supabase_store_catalog as database
from ingredient_normalization import extract_product_features
from product_compatibility import ProductMatchService
from product_ontology import FoodIdentity, compatibility, describe
from store_catalogs import MemoryRetriever, ROOT
from store_comparison import BasketComparison
from test_supabase_store_catalog import Cache


STORE = 'food_bazaar:34086'
TITLE = 'Colombina Crakenas Butter'
BASKET = {'store_ids': [STORE], 'recipes': [{'ingredients': ['8 oz rice', '2 oz butter']}]}


def feature(product_id, title, price=2, **evidence):
    return extract_product_features({
        'source': 'food-bazaar-public-staging', 'source_id': product_id, 'id': product_id,
        'name': title, 'price': f'${price:.2f}', 'unit': '16 oz', **evidence,
    })


class FixtureGateway(database.SupabaseGateway):
    def __init__(self, include_butter, feature_version):
        self.product_reads = 0
        self.metadata = next(m for m in json.loads((ROOT / 'Model/store_catalog_manifest.json').read_text())
                             if m['id'] == STORE)
        products = [
            feature('319015', 'Goya Canilla Extra Long Grain Enriched Rice', 2.09),
            feature('1392427', TITLE, 2.69, brand='Colombina', category='Crackers',
                    source_categories=['Crackers'], verified_label_text=None, unit='11.43 oz'),
        ]
        if include_butter:
            products.append(feature('19661739', 'Bogopa Unsalted Butter Quarters', 3.33))
        self.rows = []
        for i, item in enumerate(products):
            pid = item['product_id']
            identity = describe(item['original_product_name'], feature=item, product=True)
            if pid == '1392427':
                identity = FoodIdentity(family='dairy', subfamily='butter', canonical='dairy:butter',
                                        head='butter', normalized_text='crakenas butter')
            self.rows.append({
                'feature_json': item, 'identity_json': identity.to_dict(), 'source_position': i,
                'source_json': {'retailer': 'food_bazaar', 'store_id': '34086',
                                'source_url': 'https://example.test/' + pid, 'availability': True},
            })
        self.metadata['product_count'] = len(products)
        self.version = {'id': 'legacy-version', 'store_id': STORE, 'product_count': len(products),
                        'source_version': self.metadata['inventory_version'],
                        'feature_version': feature_version}

    def select(self, table, params):
        if table == 'stores':
            return [{'id': STORE, 'metadata': self.metadata}]
        if table == 'store_inventory_versions':
            return [self.version]
        assert table == 'store_products'
        self.product_reads += 1
        rows = self.rows
        for field in ('family', 'subfamily', 'semantic_head'):
            if field in params:
                values = json.loads('[' + params[field][4:-1] + ']')
                rows = [r for r in rows if r['identity_json'][field] in values]
        if 'normalized_name' in params:
            words = params['normalized_name'][7:].strip('*').split('*')
            rows = [r for r in rows if all(w in r['feature_json']['normalized_name'] for w in words)]
        offset = params.get('offset', 0)
        return copy.deepcopy(rows[offset:offset + params['limit']])


class ButterIdentityTests(unittest.TestCase):
    def test_snack_type_overrides_butter_flavor_before_matching(self):
        cases = [
            (TITLE, {'category': 'Crackers', 'source_categories': ['Crackers']}, 'cracker'),
            (TITLE, {'source_categories': None, 'subcategory': None, 'category': None}, 'cracker'),
            ('Crakeñas Butter', {'brand': 'Crakeñas'}, 'cracker'),
            ('Aster Butter', {'subcategory': 'Cookies', 'source_categories': None}, 'cookie'),
            ('Aster Butter', {'source_categories': 'Crackers'}, 'cracker'),
            ('Butter Cookies', {}, 'cookie'),
            ('Butter Flavored Chips Snack Packs', {}, 'chips'),
            ('Butter Flavored Pretzels', {}, 'prepared'),
            ('Aster Butter', {'source_categories': [None, 'Frozen Snacks']}, 'prepared'),
        ]
        for title, evidence, family in cases:
            with self.subTest(title=title, evidence=evidence):
                item = feature('test', title, **evidence)
                identity = describe(title, feature=item, product=True)
                self.assertEqual(identity.family, family)
                self.assertFalse(compatibility(describe('2 oz butter'), identity).allowed)

    def test_explicit_cracker_request_matches_the_short_title(self):
        cracker = feature('1392427', TITLE, source_categories=None)
        service = ProductMatchService(retriever=MemoryRetriever([cracker]))
        for query in ('2 oz crackers', '2 cups crackers', 'butter crackers'):
            with self.subTest(query=query):
                match = service.match_recipe_ingredient(query, use_semantic=False).selected_match
                self.assertEqual(match.product_id, '1392427')
        self.assertIsNone(service.match_recipe_ingredient('butter', use_semantic=False).selected_match)

    def test_ambiguous_flavor_and_supported_butter_forms(self):
        uncertain = describe('Aster Butter Flavor', feature={'source_categories': None}, product=True)
        self.assertTrue(uncertain.ambiguous)
        self.assertFalse(compatibility(describe('butter'), uncertain).allowed)
        for name, query in (
            ('Salted Butter Sticks', 'salted butter'),
            ('Unsalted Butter Quarters', 'unsalted butter'),
            ('European Style Cultured Butter', 'butter'),
            ('Whipped Butter', 'butter'), ('Clarified Butter', 'butter'),
            ('Cracker Barrel Butter', 'butter'),
        ):
            with self.subTest(name=name):
                identity = describe(name, feature={'source_categories': None}, product=True)
                self.assertTrue(compatibility(describe(query), identity).allowed)


class LegacyButterBasketTests(unittest.TestCase):
    def engine(self, include_butter, version, use_hot):
        gateway = FixtureGateway(include_butter, version)
        cache = database.CandidateCache(Cache())
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        manifest = root / 'Model/store_catalog_manifest.json'
        manifest.parent.mkdir()
        manifest.write_text(json.dumps([gateway.metadata]))
        with patch.object(database, 'ROOT', root):
            registry = database.DatabaseStoreRegistry(gateway, cache)
        self.addCleanup(registry.hot_cache.close)
        catalog = registry.stores[STORE]
        if not use_hot:
            catalog.hot_cache = None
        engine = BasketComparison(registry)
        self.addCleanup(engine.pool.shutdown)
        return engine, gateway, catalog

    def test_cold_and_cached_endpoint_baskets_never_price_the_cracker_as_butter(self):
        for include_butter, version in (
            (True, database.PREVIOUS_FEATURE_VERSION),
            (False, database.BUTTER_PREVIOUS_FEATURE_VERSION),
        ):
            with self.subTest(include_butter=include_butter, version=version):
                engine, gateway, catalog = self.engine(include_butter, version, use_hot=True)
                app = Flask(__name__)
                store_comparison_api.register_store_comparison(
                    app, lambda: (request.get_json(), None),
                    lambda message, code: (jsonify(error=message), code), lambda: False,
                )
                # Poison the exact old cache namespace. A runtime-only upgrade must miss it.
                with patch.object(database, 'FEATURE_VERSION', database.BUTTER_PREVIOUS_FEATURE_VERSION):
                    old_key = engine._plan(BASKET['recipes'], [catalog], False, None)[3]
                    engine.cache[old_key] = {'product_id': '1392427'}
                    catalog.hot_cache.values[catalog.hot_cache.key(catalog)] = object()
                with patch.object(store_comparison_api, '_engine', engine), app.test_client() as client:
                    cold = client.post('/api/shopping/compare', json=BASKET).get_json()
                    count = gateway.product_reads
                    cached = next(v for v in engine.cache.values() if 'basket_generation_ms' in v)
                    cached['elapsed_ms'] = 999999
                    warm = client.post('/api/shopping/compare', json=BASKET).get_json()
                self.assertEqual(gateway.product_reads, count)
                self.assertEqual(count, 1)
                self.assertFalse(cold['cache_hit'])
                self.assertTrue(warm['cache_hit'])
                self.assertEqual(cold['basket_generation_ms'], warm['basket_generation_ms'])
                self.assertLess(warm['elapsed_ms'], 999999)
                for result in (cold, warm):
                    store = result['stores'][0]
                    self.assertEqual([p['product_id'] for p in store['product_selections']],
                                     ['319015', '19661739'] if include_butter else ['319015'])
                    self.assertEqual(store['complete'], include_butter)
                    self.assertEqual(store['basket_total'], 5.42 if include_butter else None)
                    self.assertEqual(store['checkout_total_known'], 5.42 if include_butter else 2.09)
                    self.assertEqual(result['comparable_store_count'], int(include_butter))
                    self.assertEqual(store['savings_vs_other_stores'], {})
                    for selection in store['product_selections']:
                        self.assertIsNone(selection['deal']['savings_vs_closest_match'])
                        self.assertFalse(selection['deal']['best_deal'])
                        self.assertEqual(selection['deal']['comparable_candidate_count'], 1)
                    if not include_butter:
                        self.assertEqual(store['unknown_cost_items'][0]['detail'], 'NO_SAFE_MATCH')

    def test_bounded_legacy_candidates_drop_pre_fix_keys_and_rebuild_identity(self):
        engine, gateway, catalog = self.engine(False, database.PREVIOUS_FEATURE_VERSION, use_hot=False)
        query = BASKET['recipes']
        # Simulate pre-fix candidate data even though the previous runtime didn't type crackers.
        with patch.object(database, 'FEATURE_VERSION', database.BUTTER_PREVIOUS_FEATURE_VERSION):
            catalog.request_catalog(query)
        reads = gateway.product_reads
        corrected = engine.compare(query, [STORE])
        self.assertGreater(gateway.product_reads, reads)
        self.assertFalse(corrected['stores'][0]['complete'])
        prepared = catalog.request_catalog([{'ingredients': ['2 oz crackers']}])
        match = prepared.builder().match_service.match_recipe_ingredient('2 oz crackers', use_semantic=False)
        self.assertEqual(match.selected_match.product_id, '1392427')
