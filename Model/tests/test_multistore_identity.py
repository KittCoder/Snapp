"""General outer-head rules and adversarial cheap-candidate purchase safety."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ingredient_normalization import parse_ingredient
from product_ontology import describe,compatibility
from product_compatibility import ProductMatchService
from basket_quantity import BasketBuilder,canonical_quantity
from test_product_compatibility import feature,FakeRetriever

class MultistoreIdentityTests(unittest.TestCase):
 def test_white_is_not_egg_white(self):
  for text in ['white sugar','long grain white rice','white bread','white vinegar']:
   self.assertNotEqual(parse_ingredient(text).canonical_name,'eggs')
  for text in ['egg white','egg whites','whites','yolk']:
   self.assertEqual(parse_ingredient(text).canonical_name,'eggs')
 def test_ingredient_words_cannot_override_purchase_head(self):
  pairs=[('white sugar','Organic Coconut Sugar'),('butter','Broccoli Garlic Butter Sauced'),('butter','Butter Caramel'),('provolone cheese','Genoa Salame and Provolone Cheese'),('balsamic vinegar','Glaze with Balsamic Vinegar'),('olive oil','In Olive Oil Garlic'),('chickpeas','Chickpea Rotini'),('chickpeas','Chickpea Potato Warm Spices'),('oregano','Basil Garlic Oregano Paste'),('pasta','Beefaroni Pasta Bowls'),('garlic','Garlic Naan'),('milk','Milk Fudge'),('milk','Goat Milk Plain Cheese'),('eggs','Food Coloring and Easter Eggs Dyes'),('eggs','Egg Replacer'),('butter','Butter Popcorn'),('butter','Butter Beans'),('butter','Butter Cooking Spray'),('bread','Bread Fruit'),('potatoes','Scalloped Potatoes'),('chicken breast','Chicken Breast Patties'),('chicken breast','Chicken Breast Chunk in Water'),('chicken breast','Chipotle Chicken Breast Skewers')]
  for q,p in pairs:
   for brand in ['', 'Unseen Brand ']:
    with self.subTest(q=q,p=p):self.assertFalse(compatibility(describe(q),describe(brand+p,product=True)).allowed)
 def test_explicit_alternative_sugar_keeps_its_identity(self):
  self.assertTrue(compatibility(describe('coconut sugar'),describe('Organic Coconut Sugar',product=True)).allowed)
 def test_source_evidence_prevents_raw_and_animal_inference(self):
  for categories in [['Deli'],['Prepared Foods'],['Frozen Foods'],['Pantry']]:
   self.assertFalse(compatibility(describe('chicken breast'),describe('Chicken Breast',feature={'source_categories':categories},product=True)).allowed)
  self.assertFalse(compatibility(describe('ground beef'),describe('Ground Beef',feature={'verified_label_text':'MEAT FROM PLANTS'},product=True)).allowed)
 def test_wrong_but_cheap_never_reaches_optimizer(self):
  bad=feature('bad','Chickpea Rotini','chickpeas','pantry');bad['price']=.01
  good=feature('good','Chickpeas','chickpeas','pantry');good['price']=9
  svc=ProductMatchService(retriever=FakeRetriever([bad,good]));match=svc.match_recipe_ingredient('chickpeas')
  candidates=[match.selected_match]+match.compatible_alternatives
  self.assertNotIn('bad',[c.product_id for c in candidates])
  builder=BasketBuilder(svc);result=builder.optimize_ingredient_purchase(canonical_quantity(1,'pound','chickpeas'),'chickpeas',candidates,top1_product_id=match.selected_match.product_id,rejected_candidates=match.rejected_candidates)
  self.assertNotEqual(result.selected.product_id,'bad')

class CatalogV313EvidenceTests(unittest.TestCase):
 def test_remaining_outer_purchase_head_and_evidence_cases(self):
  # These are purchase-safety cases from the multi-store review, including
  # source-label/category evidence; no product ID or brand is a matching rule.
  cases=[
   ('white sugar','Palm Sugar',{}),
   ('white sugar','Date Sugar',{}),
   ('garlic','Garlic Tandoori',{}),
   ('chickpeas','Chickpea Curry',{}),
   ('rice','Long Grain Rice',{'verified_label_text':'Ready in one minute'}),
   ('milk','Whole Milk',{'source_categories':['Deli']}),
   ('milk','Whole Milk',{'source_categories':['Sweets']}),
   ('milk','Whole Milk',{'source_categories':['Breads and Bakery']}),
   ('rice','Long Grain Rice',{'source_categories':['Frozen Foods']}),
   ('onion','Yellow Onion',{'source_categories':['Pantry']}),
   ('eggs','White Eggs',{'base_unit':'gram'}),
   ('eggs','White Eggs',{'base_unit':'milliliter'}),
   ('ground beef','Ground Beef Patties',{}),
   ('chicken breast','Chicken Breast Tenderloins',{}),
   ('chicken breast','Baked Chicken Breast',{}),
   ('chicken breast','Breaded Chicken Breast',{}),
   ('chicken breast','Whole Grain Chicken Breast Strips',{}),
   ('chicken breast','Chicken Breast and Vegetable Tenders',{}),
  ]
  for query,name,metadata in cases:
   with self.subTest(query=query,product=name,metadata=metadata):
    self.assertFalse(compatibility(describe(query),describe(name,feature=metadata,product=True)).allowed)

 def test_plain_products_and_explicit_sugar_material_stay_available(self):
  cases=[('white sugar','White Granulated Cane Sugar',{}),
         ('rice','Long Grain Rice',{}),
         ('milk','Whole Milk',{}),
         ('garlic','Fresh Garlic',{}),
         ('fresh mint','Fresh Mint',{}),
         ('eggs','Large White Eggs',{'base_unit':'count'}),
         ('butter','Unsalted Butter',{}),
         ('chicken breast','Raw Chicken Breast',{'source_categories':['Meat']}),
         ('ground beef','Raw Ground Beef',{'source_categories':['Meat']}),
         ('coconut sugar','Organic Coconut Sugar',{}),
         ('palm sugar','Palm Sugar',{}),
         ('date sugar','Date Sugar',{})]
  for query,name,metadata in cases:
   with self.subTest(query=query,product=name):
    self.assertTrue(compatibility(describe(query),describe(name,feature=metadata,product=True)).allowed)

 def test_fresh_garlic_keeps_clove_quantity_context(self):
  from product_compatibility import profile_from_query
  from ingredient_normalization import parse_ingredient
  parsed=parse_ingredient('3 cloves garlic')
  self.assertEqual(parsed.quantity,3)
  self.assertEqual(parsed.unit,'clove')
  for text in ('garlic','3 cloves garlic'):
   identity=profile_from_query(text)[0].ontology
   self.assertEqual((identity.family,identity.subfamily),('produce','garlic'))
   for wrong in ('Garlic Naan','Garlic Gum','Garlic Candy'):
    with self.subTest(text=text,wrong=wrong):
     self.assertFalse(compatibility(identity,describe(wrong,product=True)).allowed)
