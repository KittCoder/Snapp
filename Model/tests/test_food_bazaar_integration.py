"""Physical inventory isolation through the shared store registry and adapter."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store_catalogs import StoreRegistry,CatalogError,digest

class FoodBazaarIntegrationTests(unittest.TestCase):
    def fixture(self,root):
        locations=[];entries=[]
        for sid,price in [('111',2.),('222',5.)]:
            location={'store_id':sid,'address':sid+' Test Street, Bronx, NY 10451','borough':'Bronx','zip_code':'10451'}
            row={'retailer':'food_bazaar','store_id':sid,'store_address':location['address'],'zip_code':'10451',
                 'source_product_id':'7','name':'White Rice','source_url':'https://shop.foodbazaar.com/store/food-bazaar/products/7-rice',
                 'scraped_at':'2026-11-05T12:00:00+00:00','price':price,'effective_current_price':price,'price_basis':'package',
                 'raw_size_text':'16 oz','package_quantity':16.,'package_unit':'oz','snap_eligible':None,'availability':True,
                 'source_metadata':{'retailer_location_id':sid,'item_id':'items_'+sid+'-7'}}
            path=root/'food_bazaar/normalized'/(sid+'.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps([row]))
            entry={**location,'retailer':'food_bazaar','status':'VERIFIED','store_name':'Food Bazaar','product_count':1,'inventory_version':digest(path),'price_coverage':100.,'package_coverage':100.}
            locations.append(location);entries.append(entry)
        (root/'food_bazaar/stores.json').write_text(json.dumps(locations));(root/'integration_ready_stores.json').write_text(json.dumps(entries))
        return entries,locations

    def test_same_source_product_keeps_each_physical_stores_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);registry=StoreRegistry(root,mw=False)
            self.assertEqual(registry.errors,[]);self.assertEqual(len(registry.stores),2)
            for sid,price in [('111',2.),('222',5.)]:
                catalog=registry.select(['food_bazaar:'+sid])[0];builder=catalog.builder()
                self.assertEqual(builder.match_service.feature_by_id['7']['price'],price)
                self.assertEqual(catalog.source_row('7')['store_id'],sid)
                self.assertFalse(builder.match_service.retriever.load_index())

    def test_relabelled_products_cannot_keep_another_stores_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);entries,locations=self.fixture(root)
            row=json.loads((root/'food_bazaar/normalized/111.json').read_text())[0]
            row['source_metadata']['retailer_location_id']='222'
            with self.assertRaisesRegex(CatalogError,'provenance'):StoreRegistry.validate_rows([row],entries[0],locations[0])

    def test_modified_inventory_is_withheld_even_when_count_and_coverage_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);path=root/'food_bazaar/normalized/111.json'
            rows=json.loads(path.read_text());rows[0]['price']=99.;path.write_text(json.dumps(rows))
            registry=StoreRegistry(root,mw=False)
            self.assertNotIn('food_bazaar:111',registry.stores);self.assertIn('food_bazaar:222',registry.stores)
            self.assertTrue(any('hash mismatch' in e['reason'] for e in registry.errors))
