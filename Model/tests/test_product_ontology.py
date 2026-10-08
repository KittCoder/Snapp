"""Independent purchase-policy corpus, hostile retrieval, and basket safety tests."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_ontology import describe,compatibility
from product_compatibility import ProductMatchService,OverrideStore,MatchCache
from product_retrieval import ProductCandidateRetriever,DeterministicEmbeddingBackend,build_product_index
from test_product_compatibility import feature,FakeRetriever,FakeBatchRetriever

CORPUS=Path(__file__).resolve().parents[1]/'evaluation/ingredient_matcher_regressions.jsonl'

class PurchasePolicyTests(unittest.TestCase):
 def test_independent_purchase_policy_corpus(self):
  for line in CORPUS.read_text().splitlines():
   case=json.loads(line)
   with self.subTest(id=case['id'],query=case['ingredient'],product=case['product_name']):
    decision=compatibility(describe(case['ingredient']),describe(case['product_name'],feature=case.get('product_feature'),product=True),case['mode'])
    accepted=decision.allowed or case['mode']=='substitute' and decision.match_type=='substitute'
    self.assertEqual(accepted,case['expected_allowed'])
    if case['group']=='substitute':self.assertEqual(decision.match_type,'substitute')
 def test_strong_semantics_and_bad_canonical_cannot_bypass_gate(self):
  bad=feature('bad','Parmesan Crackers','parmesan','cheese');bad.update(semantic=1.,lexical=1.,exact=True)
  svc=ProductMatchService(retriever=FakeRetriever([bad]))
  result=svc.match_recipe_ingredient('parmesan')
  self.assertIsNone(result.selected_match);self.assertEqual(result.match_type,'none')
  self.assertEqual(result.rejected_candidates[0].match_type,'none')
 def test_unknown_attribute_abstains_but_explicit_metadata_supplies_evidence(self):
  self.assertFalse(compatibility(describe('fresh parsley'),describe('Parsley',product=True)).allowed)
  self.assertTrue(compatibility(describe('fresh parsley'),describe('Parsley',feature={'freshness':'fresh'},product=True)).allowed)
  self.assertFalse(compatibility(describe('fresh parsley'),describe('Frozen Parsley',feature={'freshness':'fresh'},product=True)).allowed)
 def test_batch_and_cache_keep_quantity_context_and_required_identity(self):
  fs=[feature('whole','Whole Milk'),feature('skim','Fat Free Milk'),feature('dried','Nonfat Dry Milk'),feature('eggs','Eggs'),feature('pepper','White Pepper')]
  svc=ProductMatchService(retriever=FakeBatchRetriever(fs))
  qs=['1 cup whole milk','3 cups whole milk','skim milk','non-fat dry milk','1 tsp white pepper','2 eggs']
  results=svc.match_recipe_ingredients(qs,use_semantic=False)
  self.assertEqual([r.selected_match.product_id for r in results],['whole','whole','skim','dried','pepper','eggs'])
  self.assertEqual([r.raw_ingredient for r in results],qs)
  self.assertNotEqual(results[0].parsed_ingredient['quantity'],results[1].parsed_ingredient['quantity'])
  again=svc.match_recipe_ingredient('5 cups whole milk',use_semantic=False)
  self.assertTrue(again.cache_hit);self.assertEqual(again.raw_ingredient,'5 cups whole milk')
 def test_cache_and_batch_do_not_collapse_cuts_bone_salt_flavor_or_mode(self):
  svc=ProductMatchService(retriever=FakeBatchRetriever([feature('breast','Boneless Skinless Chicken Breast'),feature('wing','Chicken Wings'),feature('salt','Salted Butter'),feature('unsalt','Unsalted Butter'),feature('plain','Plain Greek Yogurt'),feature('berry','Strawberry Greek Yogurt')]))
  qs=['chicken breast','chicken wings','boneless skinless chicken breast','unsalted butter','salted butter','plain Greek yogurt','strawberry Greek yogurt']
  rs=svc.match_recipe_ingredients(qs,use_semantic=False)
  self.assertEqual([r.selected_match.product_id for r in rs],['breast','wing','breast','unsalt','salt','plain','berry'])
  from product_compatibility import profile_from_query
  keys=[svc.cache_key(profile_from_query(q)[0]) for q in qs]
  self.assertEqual(len(keys),len(set(keys)))
  strict_key=svc.cache_key(profile_from_query('parmesan')[0])
  svc.match_mode='substitute'
  self.assertNotEqual(svc.cache_key(profile_from_query('parmesan')[0]),strict_key)
 def test_substitutions_are_explicit_and_separate_from_safe_basket_alternatives(self):
  fs=[feature('pecorino','Pecorino Cheese')]
  strict=ProductMatchService(retriever=FakeRetriever(fs));opt=ProductMatchService(retriever=FakeRetriever(fs),match_mode='substitute')
  self.assertIsNone(strict.match_recipe_ingredient('parmesan').selected_match)
  chosen=opt.match_recipe_ingredient('parmesan')
  self.assertEqual(chosen.match_type,'substitute');self.assertEqual(chosen.confidence,'substitution_only');self.assertFalse(chosen.compatible_alternatives)
 def test_force_approve_and_substitution_overrides_never_bypass_identity(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'overrides.json';p.write_text(json.dumps({'version':'hostile','forced_matches':[{'query':'parmesan','product_id':'bad'}],'approved_matches':[{'query':'parmesan','product_id':'bad'}],'substitutions':[{'query':'parmesan','product_id':'bad'}]}))
   svc=ProductMatchService(retriever=FakeRetriever([feature('bad','Mozzarella Cheese')]),overrides=OverrideStore(p))
   self.assertIsNone(svc.match_recipe_ingredient('parmesan').selected_match)
 def test_package_size_price_and_recipe_units_cannot_improve_wrong_identity(self):
  fs=[feature('paste','Tomato Paste'),feature('sauce','Tomato Sauce')]
  fs[0].update(price=999,package_quantity=1,lexical=.1,semantic=.1);fs[1].update(price=.01,package_quantity=1000,lexical=1.,semantic=1.,exact=True)
  for unit in ['oz','lb','g','kg','cup','tbsp','tsp','pint','quart','gallon','can','package']:
   with self.subTest(unit=unit):
    r=ProductMatchService(retriever=FakeRetriever(fs)).match_recipe_ingredient('2 '+unit+' tomato paste')
    self.assertEqual(r.selected_match.product_id,'paste');self.assertFalse(r.compatible_alternatives)
    self.assertEqual(r.selected_match.score_breakdown['quantity_or_price'],0)
 def test_basket_cost_optimization_only_receives_structurally_compatible_products(self):
  from basket_quantity import BasketBuilder
  fs=[feature('paste','Tomato Paste'),feature('cheap','Tomato Sauce')]
  for f in fs:f.update(price=1,package_quantity=6,package_unit='ounce')
  fs[0]['price']=5
  svc=ProductMatchService(retriever=FakeBatchRetriever(fs))
  basket=BasketBuilder(match_service=svc).build_recipe_basket({'id':'ontology-basket-test','ingredients':['6 oz tomato paste']})
  self.assertEqual([x.product_id for x in basket.shopping_basket],['paste'])

class PreRetrievalGateTests(unittest.TestCase):
 def make_retriever(self,directory):
  fs=[feature('cheddar','Cheddar Cheese'),feature('wrong','Parmesan Crackers'),feature('parm','Parmesan Cheese')]
  p=Path(directory)/'features.json';p.write_text(json.dumps({'features':fs}))
  backend=DeterministicEmbeddingBackend(dimension=8);index=Path(directory)/'index'
  build_product_index(p,index,backend=backend)
  return ProductCandidateRetriever(p,index,backend=backend)
 def test_gate_applies_before_vector_scoring_and_lexical_ranking(self):
  with tempfile.TemporaryDirectory() as directory:
   retriever=self.make_retriever(directory);seen=[];original=retriever.safe_vector_scores
   def spy(matrix,vector):seen.append(len(matrix));return original(matrix,vector)
   with patch.object(retriever,'safe_vector_scores',side_effect=spy):
    result=retriever.retrieve_product_candidates('parmesan',allowed_product_ids={'parm'})
   self.assertEqual(seen,[1]);self.assertEqual([x.product_id for x in result.candidates],['parm'])
 def test_same_embedding_text_with_distinct_gates_stays_distinct_in_batch(self):
  with tempfile.TemporaryDirectory() as directory:
   retriever=self.make_retriever(directory)
   rs=retriever.retrieve_product_candidates_batch(['cheese','cheese','cheese'],allowed_product_ids=[{'parm'},{'cheddar'},set()])
   self.assertEqual([[c.product_id for c in r.candidates] for r in rs],[['parm'],['cheddar'],[]])
 def test_nonfinite_vectors_supply_no_positive_evidence(self):
  for matrix,vector in [(np.array([[float('nan'),1],[1,1]]),[1,1]),(np.ones((2,2)),[float('inf'),1])]:
   scores=ProductCandidateRetriever.safe_vector_scores(matrix,vector)
   self.assertTrue(np.isfinite(scores).all());self.assertEqual(scores[0],-1.)

if __name__=='__main__':unittest.main()
