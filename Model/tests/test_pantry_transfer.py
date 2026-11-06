import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store_comparison import BasketComparison,pantry_transfer_payload
from store_requirements import prepare_recipes
from basket_quantity import canonical_quantity
from ingredient_normalization import parse_ingredient
from test_store_comparison import FixtureRegistry,catalog

class PantryTransferTests(unittest.TestCase):
 def test_transferred_turkey_and_onions_do_not_reappear(self):
  for line in ['1 pound ground turkey breast','0.5 cup onion chopped']:
   parsed=parse_ingredient(line)
   transfer=pantry_transfer_payload([line],canonical_quantity(parsed.quantity,parsed.unit,parsed.canonical_name))
   prepared,covered=prepare_recipes([{'ingredients':[line]}],[transfer])
   self.assertEqual(prepared[0]['ingredients'],[]);self.assertEqual(covered,[line])
 def test_manual_whole_onion_covers_chopped_onion_without_erasing_meat_form(self):
  prepared,_=prepare_recipes([{'ingredients':['0.5 cup onion chopped']}],[{'name':'onion','quantity':'118.294 ml'}])
  self.assertEqual(prepared[0]['ingredients'],[])
  prepared,_=prepare_recipes([{'ingredients':['1 pound ground turkey breast']}],[{'name':'turkey breast','quantity':'1 pound'}])
  self.assertEqual(len(prepared[0]['ingredients']),1)
 def test_whole_package_transfer_retains_leftovers_across_recipe_additions(self):
  registry=FixtureRegistry();registry.stores={'a':catalog('a',4,('Cheddar Cheese',))};engine=BasketComparison(registry)
  recipe={'ingredients':['8 oz cheddar cheese']}
  first=engine.compare([recipe],['a'])['stores'][0]
  transfer=first['product_selections'][0]['pantry_transfer']
  after=engine.compare([recipe],['a'],pantry_items=[transfer])['stores'][0]
  self.assertEqual(after['basket_total'],0);self.assertEqual(after['product_selections'],[])
  more=engine.compare([recipe,{'ingredients':['6 oz cheddar cheese']}],['a'],pantry_items=[transfer])['stores'][0]
  self.assertEqual(more['basket_total'],0)
  excess=engine.compare([recipe,{'ingredients':['10 oz cheddar cheese']}],['a'],pantry_items=[transfer])['stores'][0]
  self.assertEqual(excess['basket_total'],4)
