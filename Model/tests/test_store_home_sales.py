import sys, unittest, tempfile, json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store_home_sales import store_sale_pool, _cache

class HomeSalesTests(unittest.TestCase):
 def setUp(self): _cache.clear()
 def test_local_location_isolation_and_empty_sales(self):
  with tempfile.TemporaryDirectory() as directory:
   def catalog(sid, rows):
    path=Path(directory)/sid;path.write_text(json.dumps(rows))
    return SimpleNamespace(metadata=SimpleNamespace(id=sid,inventory_version='v1',retailer='ctown'),path=path)
   def build(db):
    self.assertTrue(all(p.get('source')=='ctown-public-staging' for p in db['products']))
    return [{'ingredient_id':p['name'],'sale_price':float(p['sale_price'].lstrip('$'))} for p in db['products']]
   mw=lambda:self.fail('Must not use MW deals for another retailer')
   a=store_sale_pool(catalog('a',[{'name':'rice','sale_price':2,'regular_price':3}]),build,mw)
   b=store_sale_pool(catalog('b',[{'name':'milk','sale_price':4},{'name':'rice','sale_price':1,'availability':False}]),build,mw)
   self.assertEqual(a,[{'ingredient_id':'rice','sale_price':2,'store_id':'a'}])
   self.assertEqual(b,[{'ingredient_id':'milk','sale_price':4,'store_id':'b'}])
   self.assertEqual(store_sale_pool(catalog('empty',[]),build,mw),[])
 def test_database_queries_bind_store_and_version(self):
  calls=[]
  gateway=SimpleNamespace(select=lambda table,params:(calls.append((table,params)) or [{'source_json':{'name':'rice','sale_price':2}}]))
  c=SimpleNamespace(metadata=SimpleNamespace(id='db-a',inventory_version='v3',retailer='ctown'),version_id='version-a',gateway=gateway)
  pool=store_sale_pool(c,lambda db:db['products'],lambda:self.fail('Wrong feed'))
  self.assertEqual(pool[0]['store_id'],'db-a')
  self.assertEqual(calls[0][1]['store_id'],'eq.db-a')
  self.assertEqual(calls[0][1]['inventory_version_id'],'eq.version-a')
  self.assertEqual(calls[0][1]['or'],'(sale_price.not.is.null,feature_json->>is_on_sale.eq.true)')

 def test_imported_feature_only_sales_retain_prices_and_store_identity(self):
  import model
  from unittest.mock import patch
  feature={'original_product_name':'Mozzarella Cheese','raw_sale_price':'$2.00',
           'raw_original_price':'$3.00','raw_price':'$2.00','raw_unit_text':'16 oz','is_on_sale':True}
  calls=[]
  gateway=SimpleNamespace(select=lambda table,params:(calls.append(params) or [
      {'name':'Mozzarella Cheese','source_json':{},'feature_json':feature,
       'sale_price':None,'regular_price':None,'raw_size_text':None}]))
  c=SimpleNamespace(metadata=SimpleNamespace(id='morton-williams',inventory_version='feature-only',retailer='morton_williams'),version_id='db-version',gateway=gateway)
  artifact={'candidates':[{'ingredient_id':'mozzarella cheese','recipe_ids':['r1','r2','r3']}]}
  with patch.object(model,'load_sale_candidate_artifact',return_value=artifact):
   pool=store_sale_pool(c,lambda db:model.build_sale_ingredient_pool(db,recipe_lookup=model.artifact_recipe_ids_for_sale_ingredient),lambda:self.fail('Cannot substitute local inventory'))
  self.assertEqual(len(pool),1)
  self.assertEqual(pool[0]['store_id'],'morton-williams')
  self.assertEqual(pool[0]['sale_price'],2)
  self.assertEqual(pool[0]['original_price'],3)

class HomeSalesEndpointTests(unittest.TestCase):
 def test_requires_store_and_returns_only_selected_store(self):
  from unittest.mock import patch
  import model
  from store_catalogs import CatalogError
  catalog=SimpleNamespace(metadata=SimpleNamespace(id='a',inventory_version='v1',store_name='Store A'))
  def select(ids):
   if ids != ['a']: raise CatalogError('Unknown store')
   return [catalog]
  engine=SimpleNamespace(registry=SimpleNamespace(select=select))
  with patch('store_comparison_api.engine',return_value=engine), patch('store_home_sales.store_sale_pool',return_value=[{'ingredient_id':'rice','store_id':'a','score':1}]):
   client=model.app.test_client()
   self.assertEqual(client.get('/sale-ingredients').status_code,400)
   self.assertEqual(client.get('/sale-ingredients?store_id=invalid').status_code,400)
   response=client.get('/sale-ingredients?store_id=a')
   self.assertEqual(response.status_code,200)
   self.assertEqual(response.json['store_id'],'a')
   self.assertEqual([i['store_id'] for i in response.json['sale_ingredients']],['a'])
 def test_home_uses_prebuilt_recipe_membership_without_full_corpus_scan(self):
  from unittest.mock import patch
  import model
  product={'source':'ctown-public-staging','name':'Rice','price':'$2.00','sale_price':'$2.00','original_price':'$3.00','is_on_sale':True,'unit':'16 oz'}
  artifact={'candidates':[{'ingredient_id':'rice','recipe_ids':['r1','r2','r3']}]}
  with patch.object(model,'load_sale_candidate_artifact',return_value=artifact), patch.object(model,'sale_recipe_index',side_effect=AssertionError('Full recipe scan')):
   result=model.build_sale_ingredient_pool({'products':[product]},recipe_lookup=model.artifact_recipe_ids_for_sale_ingredient)
  self.assertTrue(result)
  self.assertEqual(result[0]['recipe_count'],3)
