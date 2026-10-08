"""General adversarial cases for the final surgical pass; no reviewed SKUs."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_ontology import describe,compatibility,IdentityCatalog
from product_compatibility import ProductMatchService
from test_product_compatibility import feature,FakeRetriever

class SurgicalStructuralTests(unittest.TestCase):
 def assert_gated(self,query,name,metadata=None):
  f=feature('candidate',name);f.update(metadata or {});f.update(semantic=1.,lexical=1.,exact=True)
  self.assertFalse(compatibility(describe(query),describe(name,feature=f,product=True)).allowed)
  catalog=IdentityCatalog([f]);self.assertNotIn('candidate',catalog.candidate_ids(describe(query)))
  r=ProductMatchService(retriever=FakeRetriever([f])).match_recipe_ingredient(query)
  self.assertIsNone(r.selected_match)
  self.assertTrue(r.rejected_candidates)
  for c in r.rejected_candidates:
   self.assertEqual(c.final_score,0);self.assertEqual(c.score_breakdown['embedding_similarity'],0)
 def test_cream_prepared_heads_precede_dairy_component(self):
  for brand in ('Unseen Market','Novel Foods Company','Different'):
   for name in ('Cream Soup','Cream of Mushroom Soup','Cream Carbonara Ramen','Creamy Noodles','Cream Crackers','Cream Cookies','Cream Pasta','Cream Flavored Snack','Creamy Cake'):
    with self.subTest(name=name,brand=brand):self.assert_gated('cream',brand+' '+name)
 def test_cream_distinct_identities_and_valid_dairy(self):
  identities=('heavy cream','light cream','sour cream','cream cheese','cream of tartar','cream of coconut')
  for q in identities:
   for p in identities:
    with self.subTest(q=q,p=p):self.assertEqual(compatibility(describe(q),describe(p,product=True)).allowed,q==p)
  for p in ('Heavy Cream','Light Cream','Whipping Cream','Cream'):
   self.assertTrue(compatibility(describe('cream'),describe('Unseen '+p,product=True)).allowed)
 def test_brown_sugar_directional_required_grade(self):
  for q in ('brown sugar','light brown sugar','dark brown sugar'):
   for p in ('Brown Sugar','Light Brown Sugar','Dark Brown Sugar'):
    for mode in ('exact','substitute'):
     with self.subTest(q=q,p=p,mode=mode):
      expected=q=='brown sugar' or q==p.lower()
      self.assertEqual(compatibility(describe(q),describe('Novel '+p,product=True),mode).allowed,expected)
  for q,p in [('dark brown sugar','Light Brown Sugar'),('light brown sugar','Dark Brown Sugar'),('dark brown sugar','Brown Sugar')]:self.assert_gated(q,'Novel '+p)
  self.assertTrue(describe('light dark brown sugar').ambiguous)
 def test_wild_rice_blends_not_pure_grain(self):
  for name in ('Long Grain and Wild Rice','Brown Rice and Wild Rice','Basmati and Wild Rice','White Rice and Wild Rice'):
   with self.subTest(name=name):self.assert_gated('raw wild rice','Novel '+name)
  self.assertTrue(compatibility(describe('wild rice'),describe('Novel Pure Wild Rice',product=True)).allowed)
 def test_unrequested_confection_processing(self):
  for name in ('Toasted Marshmallows','Marshmallows Toasted','Toasted Mini Marshmallows'):
   self.assert_gated('marshmallows','Novel '+name)
   self.assertTrue(compatibility(describe('toasted marshmallows'),describe(name,product=True)).allowed)
  self.assertTrue(compatibility(describe('marshmallows'),describe('Plain Marshmallows',product=True)).allowed)
 def test_directional_spears_not_slices(self):
  for base in ('pineapple','cucumber','carrots'):
   with self.subTest(base=base):
    self.assert_gated(base+' spears','Novel Sliced '+base)
    self.assertTrue(compatibility(describe(base+' spears'),describe('Whole '+base,product=True)).allowed)
    self.assertTrue(compatibility(describe('diced '+base),describe(base+' spears',product=True)).allowed)
 def test_compound_dessert_heads_block_fruit_components(self):
  for fruit in ('Pineapple','Strawberry','Lemon'):
   self.assert_gated(fruit+' spears','Novel '+fruit+' Cheesecake Slice')
 def test_spears_require_verified_whole_base_when_form_unknown(self):
  for fruit in ('Pineapple','Cucumber','Apple'):
   for suffix in ('Sunset','Celebration','Special Edition'):
    self.assert_gated(fruit+' spears','Unseen '+fruit+' '+suffix)
   self.assertTrue(compatibility(describe(fruit+' spears'),describe(fruit,product=True)).allowed)
 def test_replacement_prepared_and_nonfood_heads(self):
  for name in ('Lemon Scent Tall Kitchen Bags','Lemon Drawstring Bags','Lemon Garbage Bags','Lemon Trash Bags'):
   self.assert_gated('lemon','Novel '+name)
  for modifier in ('Spicy Jalapeno','Hot Chili','Serrano'):
   self.assert_gated('chili pepper','Novel '+modifier+' Queso')
  for herb in ('lemongrass','basil','ginger'):
   self.assert_gated(herb,'Novel '+herb+' Stir-In Paste')
   self.assertTrue(compatibility(describe(herb+' paste'),describe(herb+' paste',product=True)).allowed)
 def test_adobo_chili_purchase_variant_requires_evidence(self):
  for query in ('adobo chilies','chilies in adobo','adobo chili peppers'):
   for name in ('Fresh Jalapeno Peppers','Crushed Jalapeno Pepper','Canned Chili Peppers'):
    self.assert_gated(query,'Novel '+name)
  self.assertTrue(compatibility(describe('adobo chili peppers'),describe('Adobo Chili Peppers',product=True)).allowed)
 def test_white_potato_variety_requires_evidence(self):
  for name in ('Potatoes','Red Potatoes','Yellow Potatoes','Russet Potatoes'):
   self.assert_gated('white potatoes','Novel '+name)
  self.assertTrue(compatibility(describe('white potatoes'),describe('White Potatoes',product=True)).allowed)
 def test_specific_fruit_composition_is_unverified(self):
  for query in ('fruit (grapes, bananas, strawberries)','mixed fruit (apples, grapes)','fruit salad (apple, banana)'):
   self.assert_gated(query,'Novel Tropical Fruit Salad')
  self.assertTrue(compatibility(describe('mixed fruit'),describe('Mixed Fruit',product=True)).allowed)
 def test_processed_peppers_require_purchase_state(self):
  for name in ('Sliced Jalapeno Peppers','Diced Chili Peppers','Chopped Serrano Peppers'):
   self.assert_gated('diced chili pepper','Novel '+name)
  self.assertTrue(compatibility(describe('diced chili pepper'),describe('Fresh Sliced Jalapeno Peppers',product=True)).allowed)
 def test_unverified_frozen_head_and_real_compound_aliases(self):
  for fruit in ('Lemon','Pineapple','Apple'):
   self.assert_gated(fruit,'Unseen Company '+fruit+' Frozen',{'canonical_name':None,'category':None,'brand':None})
   self.assertFalse(describe('Frozen '+fruit,product=True).ambiguous)
   self.assertFalse(describe('Unseen Frozen '+fruit,feature={'brand':'Unseen'},product=True).ambiguous)
  for name in ('Lemon Grass','Lemongrass','Lemon Herb Aioli'):
   self.assert_gated('lemon','Novel '+name)
if __name__=='__main__':unittest.main()
