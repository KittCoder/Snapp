"""Architectural invariants, generated from structural classes rather than QA SKUs."""
import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_ontology import describe,compatibility,IdentityCatalog
from structural_identity_policy import Evidence,required_evidence,attribute_trace,KITCHEN_OPERATIONS,PURCHASE_DIMENSIONS
from product_compatibility import ProductMatchService,profile_from_query,rank_identity_candidate
from product_retrieval import Candidate
from test_product_compatibility import feature,FakeRetriever,FakeBatchRetriever
class StructuralConvergenceTests(unittest.TestCase):
 def test_semantic_heads_are_separate_from_modifiers(self):
  for basic,derived in [('rice','Wild Rice Cakes'),('bacon','Cheese and Bacon Mashed Potatoes'),('brown sugar','Liquid Dairy Creamer Brown Sugar'),('cream','Canned Cream Style Corn')]:
   with self.subTest(basic=basic,derived=derived):self.assertFalse(compatibility(describe(basic),describe('Unseen '+derived,product=True)).allowed)
  for name,head,form in [('salt','seasoning','basic'),('sea salt pita chips','chips','derived'),('oil','fat','basic'),('tuna in oil','fish','basic'),('spaghetti','pasta','basic'),('spaghetti squash','produce','basic'),('vanilla extract','extract','basic'),('vanilla ice cream','ice_cream','derived')]:
   with self.subTest(name=name):
    i=describe(name);self.assertEqual(i.semantic_head,head);self.assertEqual(i.identity_form,form)
 def test_generated_basic_derived_directionality_and_valid_derived_queries(self):
  for base in ('pineapple','eggplant','rice','brown sugar','chickpeas','pork liver'):
   for head in ('juice','sauce','spread','soup','cereal','pastry','chips','snack','drink','seasoning','entree'):
    with self.subTest(base=base,head=head):
     p=describe('Unseen Market '+base+' '+head,product=True)
     self.assertFalse(compatibility(describe(base),p).allowed)
     self.assertTrue(compatibility(describe(base+' '+head),p).allowed)
 def test_unknown_derived_base_never_establishes_identity(self):
  self.assertFalse(compatibility(describe('water to thin peanut sauce'),describe('Peanut Sauce',product=True)).allowed)
  self.assertTrue(compatibility(describe('vanilla ice cream'),describe('Vanilla Ice Cream',product=True)).allowed)
  self.assertFalse(compatibility(describe('vanilla ice cream'),describe('Chocolate Ice Cream',product=True)).allowed)
  for head in ('sauce','juice','spread','snack'):
   with self.subTest(head=head):self.assertFalse(compatibility(describe('unknownfood '+head),describe('unknownfood '+head,product=True)).allowed)
 def test_monotonic_specificity_and_unknown_evidence(self):
  for generic,specific in [('vinegar','raspberry vinegar'),('nuts','pine nuts'),('pasta','whole wheat pasta'),('cooking oil','extra virgin olive oil')]:
   with self.subTest(specific=specific):
    self.assertTrue(compatibility(describe(generic),describe(specific,product=True)).allowed)
    self.assertFalse(compatibility(describe(specific),describe(generic,product=True)).allowed)
  self.assertEqual(required_evidence('low_sodium',None),Evidence.UNKNOWN)
  self.assertEqual(required_evidence('low_sodium','salted'),Evidence.MISMATCH)
  self.assertEqual(required_evidence('low_sodium','low_sodium'),Evidence.MATCH)
  for query,product in [('low sodium chicken broth','Chicken Broth'),('fat free yogurt','Yogurt'),('whole grain rice','Rice'),('fresh strawberries','Strawberries')]:
   with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)
 def test_purchase_state_and_kitchen_preparation_are_explicit(self):
  for operation in ('chopped','diced','sliced'):
   with self.subTest(operation=operation):self.assertTrue(compatibility(describe(operation+' carrots'),describe('Carrots',product=True)).allowed)
  trace=attribute_trace(describe('cooked chickpeas'),describe('Chickpeas',product=True))
  self.assertEqual(trace['prepared']['policy_exception'],'kitchen_cooking')
  self.assertIn('chopped',KITCHEN_OPERATIONS);self.assertIn('state',PURCHASE_DIMENSIONS)
  for state in ('fresh','frozen','canned','dried'):
   with self.subTest(state=state):self.assertFalse(compatibility(describe(state+' cherries'),describe('Cherries',product=True)).allowed)
 def test_generated_subfamily_species_cut_and_form_matrices(self):
  groups=[('pine nuts','walnuts','almonds','Brazil nuts'),('green peas','snow peas','chickpeas','pigeon peas'),('tomato paste','tomato sauce','crushed tomatoes','diced tomatoes'),('black pepper','bell pepper','paprika','pepper sauce'),('cream','cream of tartar','cream cheese','sour cream')]
  for group in groups:
   for query in group:
    for product in group:
     if query!=product:
      with self.subTest(query=query,product=product):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)
  for species in ('beef','pork','veal','lamb'):
   for other in ('beef','pork','veal','lamb'):
    if species!=other:
     with self.subTest(species=species,other=other):self.assertFalse(compatibility(describe(species+' round steak'),describe(other+' round steak',product=True)).allowed)
 def test_nonfood_headings_and_compounds_have_hard_gates(self):
  for modifier in ('hydrating','healing','moisturizing','medicated','topical'):
   with self.subTest(modifier=modifier):self.assertFalse(compatibility(describe('cream'),describe('Unseen Cream '+modifier,product=True)).allowed)
  for query in ('For the fish:','Pico de Gallo:','Filling:','Ingredients for Broth:','marjoram and cumin','cooking liquor from salmon'):
   with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe('Salmon',product=True)).allowed)
  for product in ('Metal Polish Cream','Household Cleaner','Pasta Cooking Pan','Cherry Hard Seltzer 5% ABV'):
   with self.subTest(product=product):self.assertFalse(compatibility(describe('cream'),describe(product,product=True)).allowed)
 def test_family_pool_is_separate_from_compatible_pool(self):
  fs=[feature('plain','Whole Milk'),feature('flavored','Chocolate Milk'),feature('fish','Salmon')];catalog=IdentityCatalog(fs);q=describe('whole milk')
  self.assertIn('plain',catalog.family_candidate_ids(q));self.assertNotIn('fish',catalog.family_candidate_ids(q));self.assertNotIn('flavored',catalog.candidate_ids(q));self.assertIn('plain',catalog.candidate_ids(q))
 def test_rejected_candidate_cannot_receive_similarity_score_or_confidence(self):
  fs=[feature('bad','Mozzarella Cheese')];fs[0].update(semantic=1.,lexical=1.,exact=True)
  r=ProductMatchService(retriever=FakeRetriever(fs)).match_recipe_ingredient('parmesan')
  self.assertIsNone(r.selected_match);bad=r.rejected_candidates[0]
  self.assertEqual(bad.final_score,0);self.assertEqual(bad.score_breakdown['embedding_similarity'],0);self.assertEqual(bad.score_breakdown['token_similarity'],0);self.assertEqual(bad.confidence,'no_safe_match')
 def test_cached_selection_is_structurally_revalidated(self):
  svc=ProductMatchService(retriever=FakeRetriever([feature('milk','Whole Milk')]))
  r=svc.match_recipe_ingredient('whole milk');self.assertIsNotNone(r.selected_match)
  self.assertFalse(svc._cached_selection_is_valid(r,profile_from_query('fat free milk')[0]))
  self.assertTrue(svc._cached_selection_is_valid(r,profile_from_query('whole milk')[0]))
 def test_real_retrieval_gates_before_vector_and_batch_scoring(self):
  from test_product_ontology import PreRetrievalGateTests
  existing=PreRetrievalGateTests()
  existing.test_gate_applies_before_vector_scoring_and_lexical_ranking()
if __name__=='__main__':unittest.main()
