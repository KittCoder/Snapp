"""Each ready estimate reaches the browser without waiting for the batch."""
import threading,unittest,json
from types import SimpleNamespace
from unittest.mock import patch
import model
from store_comparison import BasketComparison
from test_store_comparison import FixtureRegistry,catalog

class StreamedPricesTests(unittest.TestCase):
    def test_http_stream_yields_price_before_calculation_finishes(self):
        finish=threading.Event()
        completed=threading.Event()
        def compare(recipes,store_id,**kwargs):
            kwargs['on_result']({'id':store_id,'recipe_id':'r','inventory_version':'v1','basket_total':4})
            finish.wait(3)
            completed.set()
        pricing=SimpleNamespace(registry=SimpleNamespace(select=lambda ids:ids),compare_recipes=compare)
        with patch('store_comparison_api.engine',return_value=pricing):
            response=model.app.test_client().post('/api/recipes/store-prices',json={'store_id':'ctown:test','recipes':[{'id':'r','ingredients':['1 cup rice']}]},headers={'Accept':'application/x-ndjson'},buffered=False)
            try:
                first=json.loads(next(iter(response.response)))
                self.assertEqual(first['price']['basket_total'],4)
                self.assertFalse(completed.is_set())
                self.assertIn('application/x-ndjson',response.content_type)
            finally:finish.set();response.close()

    def test_cached_results_publish_before_any_missing_recipe_calculation(self):
        registry=FixtureRegistry();registry.stores={"ctown:test":catalog("ctown:test",names=("Rice",))}
        engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown)
        recipes=[{'id':'a','ingredients':['1 oz rice']},{'id':'b','ingredients':['2 oz rice']}]
        engine.compare_recipes(recipes[:1],'ctown:test')
        seen=[]
        original=engine._calculate
        def calculate(*args,**kwargs):
            self.assertEqual(seen,['a'])
            return original(*args,**kwargs)
        with patch.object(engine,'_calculate',side_effect=calculate):
            engine.compare_recipes(recipes,'ctown:test',on_result=lambda p:seen.append(p['recipe_id']))
        self.assertEqual(seen,['a','b'])
