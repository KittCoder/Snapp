"""General head, specificity and stage regressions from final assistant QA."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import describe,compatibility
class ReleasePrecisionTests(unittest.TestCase):
 def test_reviewed_pairs_and_direct_aliases(self):
  for r in map(json.loads,(ROOT/'Model/evaluation/release_hardening_regressions.jsonl').open()):
   with self.subTest(case=r['case_id']):self.assertEqual(compatibility(describe(r['ingredient']),describe(r['product_name'],feature=r.get('product_feature'),product=True)).allowed,r['expected_allowed'])
 def test_prepared_food_semantic_heads(self):
  for q,p in [('white cherries','Cherries in White Chocolate'),('cranberries','Cranberry Relish'),('cooking oil','Anchovies in Olive Oil'),('salt','Multi Grain Sea Salt')]:
   with self.subTest(query=q,product=p):self.assertFalse(compatibility(describe(q),describe('Unseen '+p,product=True)).allowed)
  pairs=[('eggplant','Fried Eggplant'),('aubergine','Breaded Aubergine'),('chickpeas','Chickpea Puffs'),('salt','Sea Salt Pita Thins'),('salt','Sea Salt Pita Chips'),('cooking oil','Tuna in Oil'),('olive oil','Sardines in Olive Oil'),('vanilla essence','Vanilla Bean'),('vanilla extract','Vanilla Dessert')]
  for q,p in pairs:
   with self.subTest(query=q,product=p):self.assertFalse(compatibility(describe(q),describe('Unseen Market '+p,product=True)).allowed)
 def test_meat_species_override_inferred_cut_species(self):
  for animal in ('veal','pork','lamb'):
   for cut in ('round steak','flank steak','sirloin'):
    with self.subTest(species=animal,cut=cut):
     self.assertEqual(describe(animal+' '+cut).species,animal)
     self.assertFalse(compatibility(describe(animal+' '+cut),describe('Beef '+cut,product=True)).allowed)
  self.assertTrue(compatibility(describe('pork spareribs'),describe('Pork Spare Ribs',product=True)).allowed)
 def test_shared_specificity_cannot_disappear(self):
  for q,p in [('white cherries','Cherries'),('Italian breadcrumbs','Panko Bread Crumbs'),('Thai chili sauce','Chili Sauce'),('whole wheat pita','Pita Bread'),('whole wheat fettuccine, spaghetti, macaroni, or other noodles','Spaghetti')]:
   with self.subTest(query=q):self.assertFalse(compatibility(describe(q),describe(p,product=True)).allowed)
  for q,p in [('white cherries','White Cherries'),('Italian breadcrumbs','Italian Bread Crumbs'),('Thai chili sauce','Thai Chili Sauce'),('whole wheat pita','Whole Wheat Pita Bread')]:
   with self.subTest(query=q):self.assertTrue(compatibility(describe(q),describe(p,product=True)).allowed)
 def test_unrequested_dried_fruit_and_seed_stalk(self):
  for fruit in ('cranberries','strawberries','pineapple','apples'):
   with self.subTest(fruit=fruit):
    self.assertFalse(compatibility(describe(fruit),describe('Dried '+fruit,product=True)).allowed)
    self.assertTrue(compatibility(describe('dried '+fruit),describe('Dried '+fruit,product=True)).allowed)
  self.assertFalse(compatibility(describe('celery seed'),describe('Celery Stalks',product=True)).allowed)
  self.assertTrue(compatibility(describe('celery seed'),describe('Celery Seed',product=True)).allowed)
 def test_cooking_liquid_is_not_flesh(self):
  for fish in ('salmon','chicken','beef','fish','pork'):
   for query in ('liquor from the '+fish,'cooking liquid from '+fish):
    with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(fish,product=True)).allowed)
 def test_obvious_aliases_preserve_heads(self):
  self.assertFalse(compatibility(describe('nutmeg'),describe('The Nutmeg Spice Company Whole Black Peppercorns',product=True)).allowed)
  self.assertTrue(compatibility(describe('black peppercorns'),describe('The Nutmeg Spice Company Whole Black Peppercorns',product=True)).allowed)
  for q,p in [('kiwifruit','Kiwi'),('radishes','Red Radish'),('chopped dates','Dates Chopped'),('nuez moscada','Nutmeg'),('crushed hot red pepper','Crushed Red Pepper'),('mayonnaise low fat','Light Mayonnaise'),('hot sauce','Hot Sauce'),('vanilla essence','Vanilla Extract')]:
   with self.subTest(query=q):self.assertTrue(compatibility(describe(q),describe(p,product=True)).allowed)
if __name__=='__main__':unittest.main()
