import unittest
from ingredient_normalization import parse_ingredient
from basket_quantity import canonical_quantity,convert_quantity
from product_ontology import describe,compatibility
from store_requirements import prepare_recipes
from store_comparison import BasketComparison
from test_store_comparison import FixtureRegistry,catalog

class CountedRecipeFoodsTests(unittest.TestCase):
    def test_cherry_tomato_count_retains_variety_and_uses_household_weight(self):
        parsed=parse_ingredient('20 cherry tomatoes')
        self.assertEqual(parsed.unit,'tomato')
        weight=convert_quantity(canonical_quantity(parsed.quantity,parsed.unit),'gram','cherry tomatoes')
        self.assertEqual(weight.base_quantity,340)
        self.assertFalse(compatibility(describe('cherry tomatoes'),describe('Beefsteak Tomatoes',product=True)).allowed)
        self.assertTrue(compatibility(describe('cherry tomatoes'),describe('Cherry Tomatoes',product=True)).allowed)

    def test_nonfood_supplies_do_not_make_food_cost_incomplete(self):
        prepared,pantry=prepare_recipes([{'ingredients':['20 toothpicks','20 cherry tomatoes','2 tablespoon olive oil']}],[])
        self.assertEqual(len(prepared[0]['ingredients']),2)
        self.assertEqual(pantry,[])
        self.assertEqual(prepared[0]['recipe_supplies'],['20 toothpicks'])

    def test_pricing_cache_survives_card_to_schedule_recipe_id_and_title_changes(self):
        registry=FixtureRegistry();registry.stores={'a':catalog('a')}
        engine=BasketComparison(registry);self.addCleanup(engine.pool.shutdown)
        first=engine.compare_recipes([{'id':'card','name':'Original','ingredients':['1 oz cheddar cheese']}],'a')[0]
        second=engine.compare_recipes([{'id':'schedule','name':'Saved','ingredients':['1 oz cheddar cheese']}],'a')[0]
        self.assertTrue(second['cache_hit']);self.assertEqual(second['recipe_id'],'schedule')
        self.assertEqual(first['basket_total'],second['basket_total'])
