import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_ontology import describe,compatibility
from ingredient_normalization import contextual_ingredient_text
class ContextualIngredientUnitsTests(unittest.TestCase):
    def test_quantity_form_preserves_actual_food_head(self):
        for raw,food in [('3 cloves garlic','garlic'),('2 garlic cloves','garlic'),('1 clove garlic','garlic'),('2 heads garlic','garlic'),('4 stalks celery','celery'),('2 sprigs thyme','thyme'),('1 bunch parsley','parsley'),('3 slices rye bread','rye bread'),('2 leaves basil','basil'),('1 can tomatoes','canned tomatoes'),('2 cups rice','rice')]:
            with self.subTest(raw=raw):
                a=describe(raw);b=describe(food)
                self.assertEqual((a.family,a.subfamily),(b.family,b.subfamily))
    def test_true_clove_spice_queries_survive(self):
        for raw in ['cloves','whole cloves','ground cloves','3 whole cloves']:
            with self.subTest(raw=raw):self.assertEqual((describe(raw).family,describe(raw).subfamily),('seasoning','clove'))
    def test_garlic_count_never_matches_spice(self):
        self.assertFalse(compatibility(describe('3 cloves garlic'),describe('Whole Cloves',product=True)).allowed)
        self.assertTrue(compatibility(describe('3 cloves garlic'),describe('Garlic',product=True)).allowed)
    def test_structured_adapter_retains_garlic(self):
        from recipe_ingredient_adapter import canonical_recipe_ingredients
        r={'ingredients':[{'name':'garlic','quantity':3,'unit':'clove','raw':'3 cloves garlic'}]}
        i=canonical_recipe_ingredients(r)[0];self.assertEqual(i.ingredient_name,'garlic');self.assertEqual(describe(i.matcher_text).subfamily,'garlic')
