"""Real catalog replay: optimized products and prices equal the remote-pool reference."""
import sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[2])]
from test_store_comparison import LOCAL_CATALOGS

@unittest.skipUnless(LOCAL_CATALOGS,'Optional verified catalogs unavailable')
class RealHotCatalogTests(unittest.TestCase):
    def test_five_real_recipes_and_control_are_unchanged_with_zero_hot_searches(self):
        from scripts.benchmark_hot_store_pricing import recipes,LocalReplay,Registry
        from scripts.import_store_catalog import product_row
        from store_catalogs import StoreRegistry
        from supabase_store_catalog import DatabaseStoreCatalog,CandidateCache
        from hot_store_catalog import HotStoreCatalogCache
        from store_comparison import BasketComparison
        file=StoreRegistry().stores['ctown:PS41_311'];features=file.builder().match_service.retriever.features
        rows=[product_row(file.metadata,f,file.source_row(f['product_id']) or {},i) for i,f in enumerate(features)]
        gateway=LocalReplay(rows,file.metadata);cache=CandidateCache();cache.client=None
        legacy=DatabaseStoreCatalog(file.metadata,'version',gateway,cache)
        old=BasketComparison(Registry(legacy));self.addCleanup(old.pool.shutdown)
        batch=recipes()
        self.assertEqual(batch[0]['name'],'Healthier Actually Delicious Turkey Burgers')
        self.assertEqual(batch[1]['name'],'Healthier Kung Pao Chicken')
        expected=[old.compare([recipe],[file.metadata.id])['stores'][0] for recipe in batch]
        control={'id':'control','ingredients':['8 oz rice','2 oz butter']}
        expected_control=old.compare([control],[file.metadata.id])['stores'][0]
        hot=HotStoreCatalogCache();self.addCleanup(hot.close)
        catalog=DatabaseStoreCatalog(file.metadata,'version',gateway,cache,hot_cache=hot)
        engine=BasketComparison(Registry(catalog));self.addCleanup(engine.pool.shutdown)
        hot.get(catalog);gateway.calls.clear()
        actual=engine.compare_recipes(batch,file.metadata.id)
        self.assertEqual(gateway.calls.count('store_products'),0)
        for a,b in zip(actual,expected):
            for key in ('product_selections','basket_total','checkout_total_known','complete','unknown_cost_items','pantry_items','inventory_version'):
                self.assertEqual(a[key],b[key])
        result=engine.compare_recipes([control],file.metadata.id)[0]
        self.assertTrue(result['complete']);self.assertEqual(result['basket_total'],6.92)
        self.assertEqual(result['product_selections'],expected_control['product_selections'])
        self.assertEqual(gateway.calls.count('store_products'),0)

        second_file=StoreRegistry().stores['ctown:U41_186']
        second_features=second_file.builder().match_service.retriever.features
        second_rows=[product_row(second_file.metadata,f,second_file.source_row(f['product_id']) or {},i) for i,f in enumerate(second_features)]
        second_gateway=LocalReplay(second_rows,second_file.metadata)
        second_catalog=DatabaseStoreCatalog(second_file.metadata,'version',second_gateway,cache,hot_cache=hot)
        second_engine=BasketComparison(Registry(second_catalog));self.addCleanup(second_engine.pool.shutdown)
        hot.get(second_catalog);second_gateway.calls.clear()
        second_results=second_engine.compare_recipes(batch,second_file.metadata.id)
        self.assertEqual(second_gateway.calls.count('store_products'),0)
        self.assertTrue(all(r['id']=='ctown:U41_186' and r['inventory_version']==second_file.metadata.inventory_version for r in second_results))
        self.assertTrue(all(p['store_id']=='U41_186' for r in second_results for p in r['product_selections']))
        self.assertEqual(len(hot.values),2)
        gateway.calls.clear()
        returned=engine.compare_recipes([dict(recipe,id=recipe['id']+'-again') for recipe in batch],file.metadata.id)
        self.assertEqual(gateway.calls.count('store_products'),0)
        self.assertTrue(all(p['store_id']=='PS41_311' for r in returned for p in r['product_selections']))
