"""Store-independent alias recall with strict purchase identity boundaries."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store_catalogs import MemoryRetriever
from product_compatibility import ProductMatchService, profile_from_query
from product_ontology import describe,compatibility
from test_product_retrieval import feature


class StoreMatchingRecallTests(unittest.TestCase):
    def service(self,rows):
        return ProductMatchService(retriever=MemoryRetriever(rows))

    def test_alias_recall_in_single_and_batch_without_vectors(self):
        rows=[feature('scallion','scallions 1 bunch'),feature('beans','eden garbanzo beans')]
        for batch in (False,True):
            service=self.service(rows)
            queries=['4 green onions','1 cup chickpeas']
            results=service.match_recipe_ingredients(queries,use_semantic=False) if batch else [service.match_recipe_ingredient(q,use_semantic=False) for q in queries]
            self.assertEqual([m.selected_match.product_id for m in results],['scallion','beans'])
            self.assertFalse(service.retriever.load_index())

    def test_alias_fallback_cannot_admit_wrong_family_or_prepared_food(self):
        rows=[feature('bad-onion','onion rings'),feature('bad-beans','chickpea rotini')]
        results=self.service(rows).match_recipe_ingredients(['green onions','chickpeas'],use_semantic=False)
        self.assertTrue(all(m.selected_match is None for m in results))

    def test_juicing_instruction_preserves_purchase_identity(self):
        rows=[feature('lemon','lemon'),feature('lime','lime'),feature('candy','sour lemon drops'),feature('dip','lemon tzatziki'),feature('spray','lemon dusting spray')]
        service=self.service(rows)
        for q,pid in [('1/2 lemon juiced','lemon'),('1 lime juiced','lime')]:
            if pid=='lemon':self.assertEqual(profile_from_query(q)[0].normalized_signature,pid)
            result=service.match_recipe_ingredient(q,use_semantic=False)
            self.assertEqual(result.selected_match.product_id,pid)

    def test_fresh_herbs_require_positive_produce_evidence(self):
        query=describe('fresh parsley')
        for categories,allowed in [(['Fruits & Veggies'],True),(['Produce'],True),(['Pantry'],False),(['Spices'],False),(['Produce','Frozen Foods'],False),([],False)]:
            with self.subTest(categories=categories):
                product=describe('Italian Parsley',feature={'source_categories':categories},product=True)
                self.assertEqual(compatibility(query,product).allowed,allowed)
        self.assertFalse(compatibility(query,describe('Dried Parsley',feature={'source_categories':['Produce']},product=True)).allowed)
        self.assertFalse(compatibility(query,describe('Parsley Dressing',feature={'source_categories':['Produce']},product=True)).allowed)

    def test_seasoned_breadcrumbs_keep_the_seasoning_requirement(self):
        query=describe('seasoned bread crumbs')
        self.assertEqual(query.family,'breadcrumbs')
        for name,allowed in [('Bread Crumbs Seasoned',True),('Italian Style Bread Crumbs',True),('Plain Bread Crumbs',False),('Italian Garlic Bread Crumbs',False),('Italian Parmesan Bread Crumbs',False),('Breaded Chicken',False),('Crumb Cake',False)]:
            with self.subTest(name=name):self.assertEqual(compatibility(query,describe(name,product=True)).allowed,allowed)

    def test_preceding_snapshot_identities_are_rebuilt_from_selected_store_features(self):
        from dataclasses import asdict
        from supabase_store_catalog import RequestCatalog
        from test_supabase_store_catalog import metadata
        f=feature('parsley','Italian Parsley');f['source_categories']=['Fruits & Veggies']
        stale=asdict(describe('Italian Parsley',product=True))
        rows=[{'feature_json':f,'identity_json':stale,'source_json':{}}]
        current=RequestCatalog(metadata(),rows,rebuild_identities=True).builder().match_service
        self.assertEqual(current.identity_catalog.identities['parsley'].state,'fresh')
        self.assertIsNotNone(current.match_recipe_ingredient('fresh parsley',use_semantic=False).selected_match)

    def test_existing_lexical_candidates_keep_their_pool(self):
        rows=[feature('existing','chickpeas'),feature('alias','garbanzo beans')]
        result=self.service(rows).match_recipe_ingredient('chickpeas',use_semantic=False)
        self.assertEqual(result.selected_match.product_id,'existing')
        self.assertNotIn('alias',[m.product_id for m in result.compatible_alternatives])


class RealStoreSelectionPreservationTests(unittest.TestCase):
    def test_recovered_items_match_at_both_verified_ctown_locations(self):
        import json
        from store_catalogs import ROOT,StoreMetadata,StoreCatalog
        entries=json.loads((ROOT/'Model/store_catalog_manifest.json').read_text())
        for sid in ('ctown:PS41_311','ctown:U41_186'):
            entry=next(m for m in entries if m['id']==sid)
            path=ROOT/'data/store_scrapes/ctown/normalized'/(entry['store_id']+'.json')
            if not path.exists():self.skipTest('Optional verified C-Town snapshot unavailable')
            service=StoreCatalog(StoreMetadata(**entry),path).builder().match_service
            queries=['green onions','fresh parsley','fresh gingerroot','seasoned bread crumbs','chickpeas','1/2 lemon juiced']
            matches=service.match_recipe_ingredients(queries,use_semantic=False)
            for query,match in zip(queries,matches):
                with self.subTest(store=sid,query=query):
                    self.assertIsNotNone(match.selected_match)
                    self.assertIn(match.selected_match.product_id,service.feature_by_id)


    def test_previously_successful_morton_and_ctown_selections_do_not_change(self):
        import json
        from store_catalogs import ROOT,StoreMetadata,StoreCatalog,digest
        from basket_quantity import get_basket_builder
        fixture=json.loads((Path(__file__).parent/'fixtures/multistore_preserved_selections.json').read_text())
        path=ROOT/'data/store_scrapes/ctown/normalized/PS41_311.json'
        if not path.exists():self.skipTest('Optional verified C-Town snapshot unavailable')
        self.assertEqual(digest(path),fixture['ctown_inventory_version'])
        entry=next(m for m in json.loads((ROOT/'Model/store_catalog_manifest.json').read_text()) if m['id']==fixture['ctown_store_id'])
        ctown=StoreCatalog(StoreMetadata(**entry),path).builder().match_service
        services={'ctown':ctown,'mw':get_basket_builder().match_service}
        for store,service in services.items():
            expected=fixture['selections'][store]
            actual=service.match_recipe_ingredients(list(expected),use_semantic=False)
            for (query,pid),match in zip(expected.items(),actual):
                with self.subTest(store=store,query=query):
                    self.assertIsNotNone(match.selected_match)
                    self.assertEqual(match.selected_match.product_id,pid)

class StoreRegistryManifestTests(unittest.TestCase):
    def test_matching_manifest_skips_revalidating_other_store_rows(self):
        from unittest.mock import patch
        from store_catalogs import StoreRegistry,ROOT
        if not (ROOT/'data/store_scrapes/integration_ready_stores.json').exists():
            self.skipTest('Optional verified store snapshots unavailable')
        with patch.object(StoreRegistry,'validate_rows',wraps=StoreRegistry.validate_rows) as validate:
            registry=StoreRegistry()
        self.assertIn('ctown:PS41_311',registry.stores)
        self.assertEqual(registry.errors,[])
        self.assertEqual(validate.call_count,0)
        self.assertTrue(all(c._builder is None for c in registry.stores.values()))

    def test_changed_snapshot_hash_requires_full_validation(self):
        from unittest.mock import patch
        from store_catalogs import StoreRegistry,ROOT,digest
        path=ROOT/'data/store_scrapes/ctown/normalized/PS41_311.json'
        if not path.exists():self.skipTest('Optional verified C-Town snapshot unavailable')
        def changed_digest(p):return 'changed-snapshot' if Path(p)==path else digest(p)
        with patch('store_catalogs.digest',side_effect=changed_digest),patch.object(StoreRegistry,'validate_rows',side_effect=ValueError('unverified snapshot')) as validate:
            registry=StoreRegistry()
        self.assertEqual(validate.call_count,1)
        self.assertNotIn('ctown:PS41_311',registry.stores)
        self.assertTrue(any(e.get('store_id')=='PS41_311' for e in registry.errors if isinstance(e,dict)))
