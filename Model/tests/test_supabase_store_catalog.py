"""Bounded retrieval, credential boundaries, version isolation and migration safety."""
import copy
import json
import os
import sys
import unittest
import tempfile
import contextlib
import io
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from supabase_store_catalog import (CandidateCache, CatalogUnavailable, DatabaseStoreCatalog,
    DatabaseStoreRegistry, SupabaseGateway, FEATURE_VERSION, configured_registry, POOL_LIMIT)
from store_catalogs import StoreMetadata, CatalogError
from scripts.import_store_catalog import merge_non_null, version_id, product_row
from test_product_compatibility import feature

class Cache:
    def __init__(self):self.values={}
    def get(self,k):return self.values.get(k)
    def setex(self,k,ttl,v):self.values[k]=v

class Gateway:
    def __init__(self, rows):self.rows=rows;self.calls=[]
    def candidates(self,*args):self.calls.append(args);return copy.deepcopy(self.rows)
    def select(self,table,params):return [{'id':'version','source_version':'source','product_count':2000,'feature_version':FEATURE_VERSION}]

def metadata(sid='ctown:a'):
    return StoreMetadata(sid,'ctown',sid,'Test','A','Bronx','10462',2000,'source',None)

class DatabaseCatalogTests(unittest.TestCase):
    def registry_fixture(self):
        from store_catalogs import ROOT
        manifest = json.loads((ROOT / 'Model/store_catalog_manifest.json').read_text())
        entries = [{'id': m['id'], 'metadata': m} for m in manifest]
        versions = [{'id': 'version-' + m['id'], 'store_id': m['id'],
                     'source_version': m['inventory_version'], 'product_count': m['product_count'],
                     'feature_version': FEATURE_VERSION} for m in manifest]
        gateway = Mock()
        def select(table, params):
            if table == 'stores':
                return copy.deepcopy(entries)
            rows = versions
            if 'store_id' in params:
                rows = [v for v in versions if 'eq.' + v['store_id'] == params['store_id']]
            return copy.deepcopy(rows)
        gateway.select.side_effect = select
        return gateway, versions

    def test_matching_feature_version_initializes_registry_for_all_13_stores(self):
        gateway, versions = self.registry_fixture()
        registry = DatabaseStoreRegistry(gateway, CandidateCache(Cache()))
        self.assertEqual(len(versions), 13)
        self.assertEqual(len(registry.stores), 13)
        self.assertEqual(len(registry.public()), 13)

    def test_missing_or_null_feature_version_fails_closed(self):
        for value in ('absent', None):
            with self.subTest(value=value):
                gateway, versions = self.registry_fixture()
                if value == 'absent':
                    del versions[0]['feature_version']
                else:
                    versions[0]['feature_version'] = None
                with self.assertRaisesRegex(CatalogUnavailable, 'feature version is unavailable or stale'):
                    DatabaseStoreRegistry(gateway, CandidateCache(Cache()))

    def test_stale_or_wrong_version_type_fails_closed(self):
        for value in ('stale-fingerprint', 'ingredient-foundation-v1', 'ingredient-product-matcher-v3.9'):
            with self.subTest(value=value):
                gateway, versions = self.registry_fixture()
                versions[0]['feature_version'] = value
                with self.assertRaisesRegex(CatalogUnavailable, 'feature version is unavailable or stale'):
                    DatabaseStoreRegistry(gateway, CandidateCache(Cache()))

    def test_missing_active_inventory_version_fails_closed(self):
        gateway, versions = self.registry_fixture()
        versions.pop()
        with self.assertRaisesRegex(CatalogUnavailable, 'feature version is unavailable or stale'):
            DatabaseStoreRegistry(gateway, CandidateCache(Cache()))

    def test_probe_reports_expected_per_store_versions_and_mismatch_count(self):
        from scripts.diagnose_store_catalog import feature_version_diagnostics
        _, versions = self.registry_fixture()
        self.assertEqual(feature_version_diagnostics(versions)['feature_version_mismatch_count'], 0)
        versions[0]['feature_version'] = 'stale'
        del versions[1]['feature_version']
        versions[2]['feature_version'] = None
        report = feature_version_diagnostics(versions)
        self.assertEqual(report['expected_feature_version'], FEATURE_VERSION)
        self.assertEqual(len(report['active_feature_versions']), 13)
        self.assertEqual(report['feature_version_mismatch_count'], 3)
        self.assertEqual([v['state'] for v in report['active_feature_versions'][:3]],
                         ['mismatched', 'absent', 'null'])

    def test_cache_keys_isolate_store_inventory_identity_matcher_and_overrides(self):
        c=CandidateCache(Cache());base=c.key('a','v',{'head':'cheese'},'override')
        for args in [('b','v',{'head':'cheese'},'override'),('a','v2',{'head':'cheese'},'override'),
                     ('a','v',{'head':'rice'},'override'),('a','v',{'head':'cheese'},'different')]:
            self.assertNotEqual(base,c.key(*args))
        with patch('supabase_store_catalog.FEATURE_VERSION','future'):
            self.assertNotEqual(base,c.key('a','v',{'head':'cheese'},'override'))
    def test_request_candidates_are_isolated_bounded_and_not_retained_in_catalog(self):
        f=feature('a1','Cheddar Cheese');row={'feature_json':f,'source_json':{'source_url':'https://example.test/a','retailer':'ctown','store_id':'ctown:a'},'source_position':0}
        gateway=Gateway([row]);cache=CandidateCache(Cache());catalog=DatabaseStoreCatalog(metadata(),'version',gateway,cache)
        recipes=[{'ingredients':['8 oz cheddar cheese']}]
        request=catalog.request_catalog(recipes)
        self.assertEqual(set(request._rows),{'a1'});self.assertFalse(hasattr(catalog,'_builder'))
        self.assertEqual(gateway.calls[0][:3],('ctown:a','version','family'))
        self.assertEqual(gateway.calls[0][-1],POOL_LIMIT+1)
        catalog.request_catalog(recipes);self.assertEqual(len(gateway.calls),1);self.assertEqual(cache.hits,1)
    def test_oversize_pool_fails_instead_of_changing_winner(self):
        gateway=Gateway([{}]*(POOL_LIMIT+1));catalog=DatabaseStoreCatalog(metadata(),'version',gateway,CandidateCache(Cache()))
        with self.assertRaises(CatalogUnavailable):catalog.request_catalog([{'ingredients':['cheddar cheese']}])
    def test_empty_structured_pool_uses_public_normalized_text_fallback(self):
        gateway=Gateway([]);catalog=DatabaseStoreCatalog(metadata(),'version',gateway,CandidateCache(Cache()))
        catalog.request_catalog([{'ingredients':['cheddar cheese']}])
        self.assertEqual([c[2] for c in gateway.calls],['family','subfamily','semantic_head','normalized_name'])
    def test_cached_cross_store_rows_are_rejected(self):
        f=feature('a1','Cheddar Cheese')
        row={'feature_json':f,'source_json':{'retailer':'ctown','store_id':'other'},'source_position':0}
        catalog=DatabaseStoreCatalog(metadata(),'version',Gateway([row]),CandidateCache(Cache()))
        with self.assertRaises(CatalogUnavailable):catalog.request_catalog([{'ingredients':['cheddar cheese']}])
    def test_current_checks_active_version_and_override(self):
        catalog=DatabaseStoreCatalog(metadata(),'version',Gateway([]),CandidateCache(Cache()))
        self.assertTrue(catalog.current());catalog.version_id='old';self.assertFalse(catalog.current())
    def test_no_credentials_requires_no_network_and_explicit_db_never_falls_back(self):
        with patch.dict(os.environ,{'SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'','STORE_CATALOG_BACKEND':'supabase'}):
            with patch('requests.request') as request:
                with self.assertRaises(CatalogUnavailable):configured_registry()
                request.assert_not_called()
    def test_database_errors_do_not_leak_credentials_or_response_body(self):
        response=Mock(status_code=401,content=b'secret',text='secret')
        gateway=SupabaseGateway('https://example.test','private-key')
        with patch('requests.sessions.Session.request',return_value=response) as request:
            with self.assertRaises(CatalogUnavailable) as error:gateway.select('stores',{})
            self.assertNotIn('private-key',str(error.exception));self.assertNotIn('secret',str(error.exception))
            self.assertFalse(request.call_args.kwargs['allow_redirects'])
    def test_sql_pagination_respects_bounded_limit_and_store_version(self):
        gateway=SupabaseGateway('https://example.test','server-key')
        gateway.select=Mock(side_effect=[list(range(900)),list(range(601))])
        result=gateway.candidates('store-a','version-a','family',['cheese'],1501)
        self.assertEqual(len(result),1501)
        params=gateway.select.call_args.args[1]
        self.assertEqual(params['store_id'],'eq.store-a');self.assertEqual(params['inventory_version_id'],'eq.version-a')
        self.assertEqual(params['offset'],900);self.assertEqual(params['limit'],601)
    def test_import_null_merge_retains_nested_evidence_and_false_snap(self):
        old={'price':4,'snap_eligible':False,'feature_json':{'brand':'Rich','proof':{'url':'source'}}}
        result=merge_non_null(old,{'price':None,'snap_eligible':None,'feature_json':{'brand':None,'proof':{'url':None}}})
        self.assertEqual(result,old)
    def test_product_mapping_preserves_exact_feature_and_unknown_snap(self):
        f=feature('p1','Cheddar Cheese');row=product_row(metadata(),f,{'name':'Cheddar Cheese'},0)
        self.assertEqual(row['feature_json'],f);self.assertIsNone(row['snap_eligible'])
        self.assertEqual(row['inventory_version_id'],version_id(metadata()))
        self.assertNotEqual(version_id(metadata()),version_id(metadata('ctown:b')))
    def test_unset_backend_keeps_production_file_backed(self):
        with patch.dict(os.environ,{'SNAPP_ENV':'production'}):
            os.environ.pop('STORE_CATALOG_BACKEND',None)
            with patch('supabase_store_catalog.StoreRegistry') as files, patch('supabase_store_catalog.DatabaseStoreRegistry') as database:
                self.assertIs(configured_registry(),files.return_value)
                database.assert_not_called()
    def test_production_auto_does_not_silently_preload_file_inventories(self):
        with patch.dict(os.environ,{'STORE_CATALOG_BACKEND':'auto','SNAPP_ENV':'production','SUPABASE_SERVICE_ROLE_KEY':''}):
            with patch('supabase_store_catalog.StoreRegistry') as file_registry:
                with self.assertRaises(CatalogUnavailable): configured_registry()
                file_registry.assert_not_called()
    def test_morton_semantic_index_is_shared_with_legacy_retriever(self):
        from supabase_store_catalog import BoundedMortonRetriever
        original=Mock();original.load_index.return_value=True
        original._index_embeddings=object();original._index_metadata={'rows':[]}
        bounded=BoundedMortonRetriever([])
        with patch('supabase_store_catalog.get_basket_builder',return_value=Mock(match_service=Mock(retriever=original))):
            self.assertTrue(bounded.load_index())
        self.assertIs(bounded._index_embeddings,original._index_embeddings)
        self.assertIs(bounded._index_metadata,original._index_metadata)
        self.assertEqual(bounded.features,[])
    def test_importer_is_idempotent_reports_changes_and_activates_after_counts(self):
        from scripts import import_store_catalog as importer
        rows = {}
        versions = {}
        class ImportGateway:
            def select(self, table, params):
                return [copy.deepcopy(v) for v in rows.values() if v['store_id']==params['store_id'][3:]]
            def upsert(self, table, batch):
                target = rows if table=='store_products' else versions
                for row in batch: target[row['id']]=merge_non_null(target.get(row['id']),copy.deepcopy(row))
            def request(self, method, table, payload):
                return sum(r['inventory_version_id']==payload['target_version'] for r in rows.values())
        gateway=ImportGateway()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'features.json'
            f=feature('p1','Cheddar Cheese');source.write_text(json.dumps({'features':[f]}))
            catalogs={}
            for index in range(13):
                m=StoreMetadata('test'+str(index),'morton_williams','test'+str(index),'Test',None,None,None,1,'source',None)
                catalogs[m.id]=SimpleNamespace(metadata=m)
            registry=SimpleNamespace(stores=catalogs,errors=[])
            with patch.object(importer,'StoreRegistry',return_value=registry), patch.object(importer,'DEFAULT_FEATURES_PATH',source), contextlib.redirect_stdout(io.StringIO()):
                first=importer.run(gateway);second=importer.run(gateway)
                self.assertEqual(sum(s['inserted'] for s in first['stores']),13)
                self.assertEqual(sum(s['skipped'] for s in second['stores']),13)
                self.assertEqual(sum(s['updated'] for s in second['stores']),0)
                f['price']=7;source.write_text(json.dumps({'features':[f]}))
                third=importer.run(gateway)
                self.assertEqual(sum(s['updated'] for s in third['stores']),13)
                self.assertTrue(all(s['verified'] for s in third['stores']))
    def test_schema_has_backend_only_tables_atomic_activation_and_no_vector(self):
        sql=(Path(__file__).resolve().parents[2]/'supabase/migrations/20261016000100_store_catalog.sql').read_text()
        self.assertEqual(sql.count('ENABLE ROW LEVEL SECURITY'),3)
        self.assertIn('FROM PUBLIC,anon,authenticated',sql)
        self.assertIn('FOREIGN KEY(store_id,inventory_version_id)',sql)
        self.assertIn('expected <> actual',sql)
        self.assertNotIn('CREATE EXTENSION',sql)

if __name__=='__main__':unittest.main()
