"""Store selection, isolation, quantities, prices, cache and additive API contracts."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store_catalogs import StoreRegistry,StoreMetadata,StoreCatalog,CatalogError
from store_comparison import BasketComparison
from basket_quantity import BasketBuilder
from product_compatibility import ProductMatchService
from test_product_compatibility import FakeRetriever,feature

LOCAL_CATALOGS = (Path(__file__).resolve().parents[2]/'data/store_scrapes/integration_ready_stores.json').exists()
requires_catalogs = unittest.skipUnless(LOCAL_CATALOGS,'Optional local verified catalogs are not shipped')

class FixtureRegistry:
    def __init__(self):self.stores={}
    def select(self,ids):
        if not isinstance(ids,list) or not ids or any(i not in self.stores for i in ids):raise CatalogError('Invalid store')
        return [self.stores[i] for i in ids]

def catalog(sid,price=4,names=('Cheddar Cheese',)):
    rows=[]
    for index,name in enumerate(names):
        f=feature(sid+str(index),name);f.update(raw_price='$'+str(price),package_size='16 oz',lexical=1.,semantic=1.);rows.append(f)
    c=StoreCatalog(StoreMetadata(sid,'ctown',sid,'Test '+sid,sid+' Test St','Bronx','10462',len(rows),'version-'+sid,'2026-10-16T00:00:00+00:00'))
    c._builder=BasketBuilder(ProductMatchService(retriever=FakeRetriever(rows)));c._rows={f['product_id']:{'source_url':'https://example.com/'+f['product_id'],'availability':True} for f in rows};c.current=lambda:True
    return c

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.registry=FixtureRegistry();self.registry.stores={'a':catalog('a',4),'b':catalog('b',6)};self.engine=BasketComparison(self.registry);self.addCleanup(self.engine.pool.shutdown)
    def test_aggregate_before_purchase_and_isolate_stores(self):
        result=self.engine.compare([{'ingredients':['8 oz cheddar cheese']},{'ingredients':['10 oz cheddar cheese']}],['a','b'])
        for s in result['stores']:
            self.assertEqual(s['coverage_count'],1);self.assertEqual(len(s['product_selections']),1);self.assertEqual(s['product_selections'][0]['packages_needed'],2);self.assertTrue(s['product_selections'][0]['product_id'].startswith(s['id']))
        self.assertEqual([s['basket_total'] for s in result['stores']],[8,12]);self.assertTrue(result['stores'][0]['best_basket']);self.assertEqual(result['stores'][0]['savings_vs_other_stores'],{'b':4})
    def test_partial_missing_and_unknown_quantities_are_never_zero_cost_complete(self):
        self.registry.stores['b']=catalog('b',6,('Cheddar Cheese','Rice'))
        result=self.engine.compare([{'ingredients':['8 oz cheddar cheese','8 oz rice']}],['a','b']);self.assertEqual(result['stores'][0]['id'],'b');partial=result['stores'][1];self.assertIsNone(partial['basket_total']);self.assertEqual(partial['coverage_count'],1);self.assertFalse(partial['best_basket']);self.assertEqual(partial['savings_vs_other_stores'],{})
        r=self.engine.compare([{'ingredients':['cheddar cheese']}],['a'])['stores'][0];self.assertIsNone(r['basket_total']);self.assertEqual(len(r['unknown_cost_items']),1)
    def test_incompatible_quantity_dimensions_are_not_complete(self):
        r=self.engine.compare([{'ingredients':['8 oz cheddar cheese','10 fl oz cheddar cheese']}],['a'])['stores'][0];self.assertIsNone(r['basket_total'])
    def test_cache_separates_store_and_quantity_and_rejects_changed_inventory(self):
        recipe=[{'ingredients':['8 oz cheddar cheese']}];first=self.engine.compare(recipe,['a']);self.assertFalse(first['cache_hit']);second=self.engine.compare(recipe,['a']);self.assertTrue(second['cache_hit']);second['stores'][0]['basket_total']=999;self.assertNotEqual(self.engine.compare(recipe,['a'])['stores'][0]['basket_total'],999)
        self.assertNotEqual(first['basket_id'],self.engine.compare(recipe,['b'])['basket_id']);self.assertNotEqual(first['basket_id'],self.engine.compare([{'ingredients':['18 oz cheddar cheese']}],['a'])['basket_id'])
        self.registry.stores['a'].current=lambda:False
        with self.assertRaises(CatalogError):self.engine.compare(recipe,['a'])
    def test_feature_contamination_fails_closed(self):
        self.registry.stores['a']._rows={'other-store-id':{}}
        with self.assertRaises(CatalogError):self.engine.compare([{'ingredients':['8 oz cheddar cheese']}],['a'])
    def test_morton_williams_uses_existing_builder_and_same_purchase(self):
        c=self.registry.stores['a'];m=c.metadata;c.metadata=StoreMetadata('morton-williams','morton_williams',m.store_id,m.store_name,m.address,m.borough,m.zip_code,m.product_count,m.inventory_version,m.verified_at)
        with patch('store_catalogs.get_basket_builder',return_value=c._builder):
            recipes=[{'ingredients':['18 oz cheddar cheese']}];before=c._builder.build_multi_recipe_basket(recipes,use_semantic=False);after=self.engine.store_basket(c,recipes)
        self.assertEqual(after['product_selections'][0]['product_id'],before.shopping_basket[0].product_id);self.assertEqual(after['basket_total'],before.checkout_cost)

class RegistryTests(unittest.TestCase):
    @requires_catalogs
    def test_actual_whitelist_exactly_12_and_named_stores(self):
        r=StoreRegistry();self.assertEqual(len([s for s in r.stores if s.startswith('ctown:')]),12);self.assertEqual(r.errors,[])
        for sid in ['PS41_311','U41_131','U41_205']:self.assertIn('ctown:'+sid,r.stores)
        for bad in ['ctown:PS41_029','key_food:2498','food_bazaar:31555','../../etc/passwd','ctown:../PS41_311']:
            with self.assertRaises(CatalogError):r.select([bad])
    def test_corrupt_count_and_cross_store_rows_rejected(self):
        entry={'store_id':'A','product_count':1,'price_coverage':100.,'package_coverage':100.};location={'address':'1 Test St','zip_code':'10462'}
        row={'retailer':'ctown','store_id':'B','store_address':'1 Test St','zip_code':'10462'}
        for rows in [[],[row]]:
            with self.assertRaises(CatalogError):StoreRegistry.validate_rows(rows,entry,location)
    def test_missing_verified_artifact_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'ctown').mkdir();e={'retailer':'ctown','status':'VERIFIED','store_id':'A','address':'1 Test St','borough':'Bronx','store_name':'C-Town','product_count':1};(root/'integration_ready_stores.json').write_text(json.dumps([e]));(root/'ctown/stores.json').write_text(json.dumps([dict(e,zip_code='10462')]))
            r=StoreRegistry(root,mw=False);self.assertEqual(r.public(),[]);self.assertEqual(len(r.errors),1)

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ['SNAPP_DISABLE_MATCHER_WARMUP']='1'
        import model
        cls.client=model.app.test_client()
    def test_store_path_injection_and_partial_ids_rejected(self):
        for sid in ['../../etc/passwd','ctown:PS41_029','food_bazaar:31555']:
            r=self.client.post('/api/shopping/compare',json={'store_ids':[sid],'recipes':[{'ingredients':['8 oz rice']}]});self.assertEqual(r.status_code,400)
    @requires_catalogs
    def test_registry_and_preflight(self):
        r=self.client.get('/api/stores');self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['stores']),13);self.assertNotIn('catalog_path',r.json['stores'][0]);self.assertEqual(self.client.options('/api/shopping/compare').status_code,204)
    @requires_catalogs
    def test_valid_comparison_request_uses_only_selected_store(self):
        r=self.client.post('/api/shopping/compare',json={'store_ids':['ctown:PS41_311'],'recipes':[{'ingredients':['8 oz rice']} ]})
        self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['stores']),1);store=r.json['stores'][0];self.assertEqual(store['id'],'ctown:PS41_311');self.assertTrue(all(p['store_id']=='PS41_311' and p['snap_eligible'] is None for p in store['product_selections']));self.assertFalse(store['best_basket'])
    def test_malformed_and_unbounded_requests_are_rejected(self):
        for recipe in [{'ingredients':42},{'ingredients':[]},{'ingredients':['x'*1001]}]:
            r=self.client.post('/api/shopping/compare',json={'store_ids':['morton-williams'],'recipes':[recipe]});self.assertEqual(r.status_code,400)

class AdditionalCacheTests(unittest.TestCase):
    def test_same_product_ids_in_two_stores_keep_distinct_prices(self):
        registry=FixtureRegistry()
        for sid,price in [('a',4),('b',6)]:
            c=catalog(sid,price);f=feature('shared','Cheddar Cheese');f.update(raw_price='$'+str(price),package_size='16 oz',lexical=1.,semantic=1.);c._builder=BasketBuilder(ProductMatchService(retriever=FakeRetriever([f])));c._rows={'shared':{'source_url':'https://example.com/'+sid}};registry.stores[sid]=c
        engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown);r=engine.compare([{'ingredients':['8 oz cheddar cheese']}],['a','b']);self.assertEqual([s['basket_total'] for s in r['stores']],[4,6])
    def test_optimizer_and_inventory_versions_change_cache_key(self):
        registry=FixtureRegistry();registry.stores={'a':catalog('a')};engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown);recipes=[{'ingredients':['8 oz cheddar cheese']}];key=engine.compare(recipes,['a'])['basket_id']
        with patch('store_comparison.DEAL_OPTIMIZER_VERSION','new-optimizer'):
            other=engine.compare(recipes,['a']);self.assertNotEqual(key,other['basket_id']);self.assertFalse(other['cache_hit'])
        from dataclasses import replace
        registry.stores['a'].metadata=replace(registry.stores['a'].metadata,inventory_version='changed');self.assertNotEqual(key,engine.compare(recipes,['a'])['basket_id'])

class RuntimeCacheTests(unittest.TestCase):
    def test_ctown_has_no_access_to_morton_vector_index(self):
        from store_catalogs import MemoryRetriever
        from product_retrieval import DEFAULT_INDEX_DIR
        r=MemoryRetriever([]);self.assertFalse(r.load_index());self.assertNotEqual(r.index_dir,DEFAULT_INDEX_DIR)
    @requires_catalogs
    def test_whitelist_change_revokes_cached_store_choices(self):
        registry=StoreRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            registry.root=Path(tmp);(registry.root/'integration_ready_stores.json').write_text('[]')
            with self.assertRaises(CatalogError):registry.select(['ctown:PS41_311'])
            with self.assertRaises(CatalogError):registry.public()
    @requires_catalogs
    def test_cached_identity_equals_existing_ontology(self):
        from product_ontology import describe
        registry=StoreRegistry();service=registry.stores['ctown:PS41_311'].builder().match_service
        for feature_row in list(service.retriever.eligible_features)[:30]:
            expected=describe(feature_row.get('original_product_name') or feature_row.get('normalized_name'),feature=feature_row,product=True)
            self.assertEqual(service.identity_catalog.identities[feature_row['product_id']],expected)
