"""Hot-store isolation, single-flight loading and exact legacy retrieval parity."""
import copy,json,sys,threading,unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hot_store_catalog import HotStoreCatalogCache
from supabase_store_catalog import DatabaseStoreCatalog,SupabaseGateway,CandidateCache,CatalogUnavailable
import supabase_store_catalog as db
from store_catalogs import StoreMetadata,CatalogError
from store_comparison import BasketComparison
from product_ontology import describe
from test_product_compatibility import feature

class Gateway(SupabaseGateway):
    def __init__(self):self.rows={};self.catalogs={};self.calls=[]
    def select(self,table,params):
        self.calls.append((table,dict(params)))
        sid=params['store_id'][3:];c=self.catalogs[sid]
        if table=='store_inventory_versions':return [{'id':c.version_id,'source_version':c.metadata.inventory_version,'product_count':c.metadata.product_count,'feature_version':db.FEATURE_VERSION}]
        rows=self.rows[sid]
        for field in ('family','subfamily','semantic_head'):
            if field in params:
                values=json.loads('['+params[field][4:-1]+']');rows=[r for r in rows if r['identity_json'].get(field) in values]
        offset=params.get('offset',0)
        return copy.deepcopy(rows[offset:offset+params.get('limit',900)])

class Registry:
    def __init__(self,catalogs):self.stores={c.metadata.id:c for c in catalogs}
    def select(self,ids):
        if not isinstance(ids,list) or any(i not in self.stores for i in ids):raise CatalogError('Invalid store')
        return [self.stores[i] for i in ids]
    def all_current(self,cs):return all(c.current() for c in cs)

class HotStoreTests(unittest.TestCase):
    def setUp(self):
        self.gateway=Gateway();self.hot=HotStoreCatalogCache(2);self.addCleanup(self.hot.close)
    def catalog(self,sid='ctown:a',price=4,hot=True):
        metadata=StoreMetadata(sid,'ctown',sid,'Store '+sid,'Test street','Bronx','10462',2,'source-v1',None)
        rows=[]
        for index,name in enumerate(['Rice','Butter']):
            f=feature('shared-'+str(index),name);f.update(raw_price='$'+str(price),package_size='16 oz',lexical=1.,semantic=1.)
            rows.append({'feature_json':f,'identity_json':asdict(describe(name,feature=f,product=True)),
                         'source_position':index,'source_json':{'retailer':'ctown','store_id':sid,'source_url':'https://example.test/'+sid,'unused_blob':'omit me'}})
        c=DatabaseStoreCatalog(metadata,'database-v1',self.gateway,CandidateCache(),hot_cache=self.hot if hot else None)
        self.gateway.rows[sid]=rows;self.gateway.catalogs[sid]=c
        return c
    def products(self):return [p for table,p in self.gateway.calls if table=='store_products']
    def engine(self,cs):
        e=BasketComparison(Registry(cs));self.addCleanup(e.pool.shutdown);return e
    def test_bulk_once_and_zero_hot_product_queries(self):
        c=self.catalog();e=self.engine([c]);self.hot.get(c);self.assertEqual(len(self.products()),1)
        self.gateway.calls.clear()
        recipes=[{'id':str(i),'ingredients':['8 oz rice','2 oz butter']} for i in range(5)]
        result=e.compare_recipes(recipes,c.metadata.id)
        self.assertEqual(len(self.products()),0);self.assertEqual(len(result),5)
        self.assertEqual([r['basket_total'] for r in result],[8]*5)
        self.assertEqual(len([t for t,p in self.gateway.calls if t=='store_inventory_versions']),1)
        e.compare_recipes(recipes,c.metadata.id);self.assertEqual(len(self.products()),0)
        self.assertNotIn('unused_blob',self.hot.get(c)._rows['shared-0'])
    def test_concurrent_load_is_single_flight(self):
        c=self.catalog()
        with ThreadPoolExecutor(max_workers=5) as pool:values=list(pool.map(lambda _:self.hot.get(c),range(5)))
        self.assertEqual(len(self.products()),1);self.assertTrue(all(v is values[0] for v in values))
    def test_inventory_and_feature_versions_invalidate(self):
        c=self.catalog();first=self.hot.get(c)
        c.version_id='database-v2';c.metadata=replace(c.metadata,inventory_version='source-v2')
        second=self.hot.get(c);self.assertIsNot(first,second);self.assertEqual(len(self.products()),2)
        with patch('supabase_store_catalog.FEATURE_VERSION','future'):
            third=self.hot.get(c);self.assertIsNot(second,third)
        self.assertEqual(len(self.products()),3)
    def test_lru_evicts_the_least_recent_store(self):
        a,b,c=[self.catalog('ctown:'+x) for x in 'abc']
        self.hot.get(a);self.hot.get(b);self.hot.get(a);self.hot.get(c)
        self.assertEqual([key[0] for key in self.hot.values],['ctown:a','ctown:c'])
        self.assertEqual(len(self.hot.values),2);self.hot.get(b);self.assertEqual(len(self.hot.values),2)
    def test_cross_store_rows_and_bad_count_fail_closed(self):
        c=self.catalog();self.gateway.rows[c.metadata.id][0]['source_json']['store_id']='other'
        with self.assertRaises(CatalogUnavailable):self.hot.get(c)
        self.gateway.rows[c.metadata.id][0]['source_json']['store_id']=c.metadata.id
        c.metadata=replace(c.metadata,product_count=3)
        with self.assertRaises(CatalogUnavailable):self.hot.get(c)
        self.assertEqual(len(self.hot.values),0)
    def test_shared_ids_never_share_store_prices_or_versions(self):
        a,b=self.catalog('ctown:a',4),self.catalog('ctown:b',7);e=self.engine([a,b])
        for c,total in [(a,8),(b,14)]:
            self.hot.get(c);self.gateway.calls.clear();r=e.compare_recipes([{'id':'r','ingredients':['8 oz rice','2 oz butter']}],c.metadata.id)[0]
            self.assertEqual(r['basket_total'],total);self.assertEqual(r['id'],c.metadata.id);self.assertEqual(r['inventory_version'],c.metadata.inventory_version);self.assertEqual(self.products(),[])
    def test_matches_shared_once_and_outputs_equal_reference(self):
        hot=self.catalog();remote=DatabaseStoreCatalog(hot.metadata,hot.version_id,self.gateway,CandidateCache())
        recipes=[{'id':str(i),'ingredients':['8 oz rice','2 oz butter','8 oz rice']} for i in range(5)]
        old=self.engine([remote]);reference=[old.compare([recipe],[remote.metadata.id])['stores'][0] for recipe in recipes]
        e=self.engine([hot]);service=self.hot.get(hot).builder().match_service
        with patch.object(service,'match_recipe_ingredients',wraps=service.match_recipe_ingredients) as matches:
            result=e.compare_recipes(recipes,hot.metadata.id)
        self.assertEqual(matches.call_count,1)
        self.assertEqual(len(matches.call_args.args[0]),2)
        for actual,expected in zip(result,reference):
            for field in ('product_selections','basket_total','complete','unknown_cost_items','pantry_items'):
                self.assertEqual(actual[field],expected[field])
    def test_warm_endpoint_validates_id_and_starts_background_load(self):
        import model
        c=self.catalog();e=self.engine([c]);client=model.app.test_client()
        with patch('store_comparison_api.engine',return_value=e):
            self.assertEqual(client.post('/api/stores/warm',json={'store_id':'bad'}).status_code,400)
            response=client.post('/api/stores/warm',json={'store_id':c.metadata.id})
            self.assertIn(response.status_code,(200,202));self.hot.get(c)
            self.assertEqual(client.post('/api/stores/warm',json={'store_id':c.metadata.id}).json['status'],'hot')

    def test_persisted_identity_reuse_preserves_product_profile(self):
        from product_compatibility import profile_from_feature
        c=self.catalog();prepared=self.hot.get(c);service=prepared.builder().match_service
        for f in service.retriever.features:
            self.assertEqual(asdict(service.product_profile(f)),asdict(profile_from_feature(f)))

    def test_semantic_requirements_use_one_embedding_batch(self):
        import numpy as np
        from types import SimpleNamespace
        c=self.catalog('morton-williams');c.metadata=replace(c.metadata,retailer='morton_williams')
        original=Mock();original.load_index.return_value=True
        original._index_embeddings=np.asarray([[1.,0.],[0.,1.]])
        original._index_metadata={'index_version':'fixture','rows':[{'product_id':'shared-0','normalized_name':'rice','record_status':'valid'},{'product_id':'shared-1','normalized_name':'butter','record_status':'valid'}]}
        backend=SimpleNamespace(model_version='fixture',embed=Mock(side_effect=lambda texts,**kw:np.asarray([[1.,0.] for _ in texts])))
        original.backend=backend
        legacy=SimpleNamespace(match_service=SimpleNamespace(retriever=original,product_index_version=lambda:'fixture'))
        with patch('supabase_store_catalog.get_basket_builder',return_value=legacy):
            e=self.engine([c]);e.compare_recipes([{'id':str(i),'ingredients':['8 oz rice','2 oz butter']} for i in range(5)],c.metadata.id,mw_semantic=True)
        self.assertEqual(backend.embed.call_count,1)
        self.assertEqual(len(backend.embed.call_args.args[0]),2)

    def test_activation_during_load_never_installs_an_old_snapshot(self):
        c=self.catalog()
        with patch.object(c,'current',side_effect=[True,False]):
            with self.assertRaises(CatalogUnavailable):self.hot.get(c)
        self.assertFalse(self.hot.is_hot(c))

    def test_changed_active_version_rejects_even_completed_prices(self):
        c=self.catalog();e=self.engine([c]);recipes=[{'id':'r','ingredients':['8 oz rice']}]
        e.compare_recipes(recipes,c.metadata.id)
        with patch.object(c,'current',return_value=False):
            with self.assertRaises(CatalogError):e.compare_recipes(recipes,c.metadata.id)
