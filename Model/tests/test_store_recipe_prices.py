"""Quantity round trips, independent chat batches and real-catalog price provenance."""
import json,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recipe_ingredient_adapter import canonical_recipe_ingredients
from store_requirements import prepare_recipes
from basket_quantity import recipe_ingredients
from store_comparison import BasketComparison
from test_store_comparison import FixtureRegistry,catalog,LOCAL_CATALOGS
import model


class QuantityRoundTripTests(unittest.TestCase):
    def test_detail_measure_display_roundtrip_retains_quantity(self):
        original={'id':'r','title':'Rice and butter','extendedIngredients':[{'name':'rice','original':'8 oz rice'},{'name':'butter','original':'2 oz butter'}]}
        detail=model.spoonacular_recipe_from_recipe(original)
        saved=json.loads(json.dumps(detail))
        self.assertEqual(recipe_ingredients(saved)[1],['8 ounce rice','2 ounce butter'])
        self.assertEqual([(i.quantity,i.unit) for i in canonical_recipe_ingredients(saved)],[(8,'ounce'),(2,'ounce')])

    def test_servings_half_double_and_no_double_scaling(self):
        source={'ingredients':[{'name':'ground beef','display':'1 lb ground beef'}],'source_servings':4}
        for target,quantity in [(2,.5),(8,2)]:
            prepared,_=prepare_recipes([dict(source,target_servings=target)])
            parsed=canonical_recipe_ingredients(prepared[0])[0]
            self.assertEqual(parsed.quantity,quantity)
            # Preparation removes scaling intent so repeated preparation is idempotent.
            again,_=prepare_recipes(prepared)
            self.assertEqual(again[0]['ingredients'],prepared[0]['ingredients'])

    def test_water_configured_spices_and_quantity_aware_pantry(self):
        recipes=[{'ingredients':['2 cups water','1 tsp salt','1 tsp black pepper','8 oz rice']}]
        prepared,pantry=prepare_recipes(recipes,[{'name':'salt','quantity':'1 tsp'},{'name':'black pepper','quantity':'1 tsp'},{'name':'rice','quantity':'4 oz'}])
        self.assertEqual(prepared[0]['ingredients'],['4 ounce rice'])
        self.assertEqual(len(pantry),3)
        bottled,_=prepare_recipes([{'ingredients':['1 bottle mineral water']}])
        self.assertTrue(bottled[0]['ingredients'])

    def test_duplicate_requirements_keep_both_quantities_until_basket_aggregation(self):
        registry=FixtureRegistry();registry.stores={'ctown:PS41_311':catalog('ctown:PS41_311',4,('Rice',))}
        engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown)
        result=engine.compare([{'ingredients':['8 oz rice','10 oz rice']}],['ctown:PS41_311'])['stores'][0]
        self.assertEqual(len(result['product_selections']),1)
        self.assertEqual(result['product_selections'][0]['packages_needed'],2)
        self.assertEqual(result['basket_total'],8)


class RecipeBatchTests(unittest.TestCase):
    def setUp(self):
        self.registry=FixtureRegistry();self.registry.stores={'ctown:PS41_311':catalog('ctown:PS41_311',4,('Rice','Butter'))}
        self.engine=BasketComparison(self.registry);self.addCleanup(self.engine.pool.shutdown)
        self.client=model.app.test_client()
        self.patch=patch('store_comparison_api.engine',return_value=self.engine);self.patch.start();self.addCleanup(self.patch.stop)

    def test_one_batch_has_five_independent_baskets_and_store_provenance(self):
        recipes=[{'id':str(i),'ingredients':['8 oz rice','2 oz butter']} for i in range(5)]
        response=self.client.post('/api/recipes/store-prices',json={'store_id':'ctown:PS41_311','recipes':recipes})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(len(response.json['prices']),5)
        for price in response.json['prices']:
            self.assertEqual(price['basket_total'],8)
            self.assertEqual(price['id'],'ctown:PS41_311')
            self.assertTrue(all(p['product_id'].startswith('ctown:PS41_311') for p in price['product_selections']))

    def test_all_pantry_recipe_requires_no_purchase(self):
        result=self.engine.compare([{'ingredients':['2 cups water','1 tsp salt']}],['ctown:PS41_311'],pantry_items=[{'name':'salt','quantity':'1 tsp'}])['stores'][0]
        self.assertTrue(result['complete'])
        self.assertEqual(result['basket_total'],0)
        self.assertEqual(len(result['pantry_items']),2)
        self.assertEqual(result['unknown_cost_items'],[])

    def test_scaling_inventory_and_store_change_cache_keys(self):
        from dataclasses import replace
        recipe={'id':'r','ingredients':['8 oz rice'],'source_servings':4,'target_servings':2}
        a=self.engine.compare([recipe],['ctown:PS41_311'])
        b=self.engine.compare([dict(recipe,target_servings=8)],['ctown:PS41_311'])
        self.assertNotEqual(a['basket_id'],b['basket_id'])
        self.assertTrue(self.engine.compare([recipe],['ctown:PS41_311'])['cache_hit'])
        c=self.registry.stores['ctown:PS41_311'];c.metadata=replace(c.metadata,inventory_version='new')
        self.assertNotEqual(a['basket_id'],self.engine.compare([recipe],['ctown:PS41_311'])['basket_id'])

    def test_invalid_and_unbounded_batch(self):
        for payload in [{'store_id':'bad','recipes':[{'ingredients':['8 oz rice']}]},{'store_id':'ctown:PS41_311','recipes':[{'ingredients':['8 oz rice']}]*11}]:
            self.assertEqual(self.client.post('/api/recipes/store-prices',json=payload).status_code,400)


@unittest.skipUnless(LOCAL_CATALOGS,'Local verified catalogs unavailable')
class RealRecipeEndToEndTests(unittest.TestCase):
    def test_real_control_detail_recovers_two_known_prices(self):
        from store_catalogs import StoreRegistry
        engine=BasketComparison(StoreRegistry());self.addCleanup(engine.pool.shutdown)
        original={'id':'control','extendedIngredients':[{'name':'rice','original':'8 oz rice'},{'name':'butter','original':'2 oz butter'}]}
        detail=model.spoonacular_recipe_from_recipe(original)
        before=engine.compare([{'ingredients':['rice','butter']}],['ctown:PS41_311'])['stores'][0]
        after=engine.compare([detail],['ctown:PS41_311'])['stores'][0]
        self.assertEqual(before['checkout_total_known'],0)
        self.assertFalse(before['complete'])
        self.assertTrue(after['complete'])
        self.assertEqual(after['basket_total'],6.92)
        self.assertEqual(len([p for p in after['product_selections'] if p['checkout_cost'] is not None]),2)


    def test_real_recipe_chat_detail_schedule_and_shopping_agree(self):
        from recipe_search_typesense import recipe_to_typesense_document
        from store_catalogs import StoreRegistry
        rows=json.loads((Path(__file__).resolve().parents[1]/'all_recipes.json').read_text())['recipes']
        source=next(r for r in rows if r['id']=='c523878712b0658d')
        document=recipe_to_typesense_document(dict(source,title=source['name']))
        import recipe_chat
        import recipe_search_typesense as search
        from test_recipe_chat import Wire
        wire=Wire();wire.documents=[document]
        with patch.object(search,'typesense_request',side_effect=wire):
            response=recipe_chat.RecipeChatService().handle_message('rice',None)
        chat=response['results'][0]
        self.assertEqual(chat['id'],document['id'])
        search_call=next(c for c in wire.calls if c[0]=='POST')
        self.assertIn('ingredients_text',search_call[2]['searches'][0]['include_fields'])
        self.assertEqual(len(chat['ingredients_text']),4)
        with patch('recipe_chat.configured_service'),patch('recipe_search_typesense.get_recipe_by_id',return_value=document),patch.object(model,'match_recipe_ingredients_to_morton_williams',return_value=[]),patch.object(model,'morton_williams_store_lookup',return_value={}):
            response=model.app.test_client().post('/api/recipes/detail',json={'recipe_id':document['id'],'for_schedule':True})
        self.assertEqual(response.status_code,200,response.json)
        saved=json.loads(json.dumps(response.json['dish']))
        self.assertEqual(len(saved['recipe']['ingredients']),4)
        pantry=[{'name':'salt','quantity':'1 tsp'}]
        chat_recipe={'id':chat['id'],'ingredients':chat['ingredients_text'],'source_servings':3,'target_servings':3}
        shopping_recipe=dict(saved['recipe'],source_servings=3,target_servings=3)
        engine=BasketComparison(StoreRegistry());self.addCleanup(engine.pool.shutdown)
        totals=[]
        for sid in ['ctown:PS41_311','ctown:U41_186','morton-williams']:
            first=engine.compare([chat_recipe],[sid],pantry_items=pantry)['stores'][0]
            second=engine.compare([shopping_recipe],[sid],pantry_items=pantry)['stores'][0]
            self.assertEqual(first['inventory_version'],second['inventory_version'])
            self.assertEqual(first['basket_total'],second['basket_total'])
            self.assertEqual(first['checkout_total_known'],second['checkout_total_known'])
            self.assertEqual([p['product_id'] for p in first['product_selections']],[p['product_id'] for p in second['product_selections']])
            totals.append((sid,first['basket_total'],first['checkout_total_known']))
        print('Real Rice recipe chat / Shopping:',totals)
