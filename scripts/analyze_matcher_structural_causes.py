#!/usr/bin/env python3
"""Case-level diagnostic attribution. These tables are never matcher overrides."""
import collections,csv,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import describe,compatibility
OUT=ROOT/'data/matcher_structural_audit';OUT.mkdir(exist_ok=True)
rows=list(csv.DictReader((ROOT/'data/matcher_validation/review_assistant_labeled.csv').open()))
features=json.loads((ROOT/'Model/morton_williams_product_features.json').read_text())['features'];byid={r['product_id']:r for r in features}
# Explicit diagnostic adjudications from review notes and actual inventory names.
# IDs belong only to evaluation evidence, never production matching.
EXPECTED_OVERRIDES={
 'cf6fe32dcb1b9871e45e':['mw_10b4232a64ce46dd'],
 '1fee214c9ad8b502a400':['mw_a3f38c7b4b76dd39','mw_27b28ddc1458bb2a'],
 '96ffe719a3b819a2fd4e':['mw_27d15182ff85bed4'],
 '0e3fc7545ac5f3091ed3':['mw_27d15182ff85bed4'],
 '1435d80d21640f1acb68':['mw_257ca58d74d82f91'],
 'f38585d63f356757d138':['mw_9434027b685c1375','mw_9bf998dc6ddbc4c1'],
 '927652f6e486ea2c6a0e':['mw_eb540e3757ccc200'],
 'e9655c015024255be5de':['mw_87c1e93b7834320a'],
}
CAUSE_NAMES=['PREPARED_FOOD_LEAKAGE','COMPOUND_NOUN / HEAD_NOUN_COLLISION','WRONG_FAMILY','WRONG_SUBFAMILY','WRONG_SPECIES','WRONG_CUT','WRONG_FORM_OR_STATE','REQUIRED_VARIANT_DROPPED','GENERIC_VS_SPECIFIC_ASYMMETRY','FLAVOR_ATTRIBUTE_LEAK','FAT_SALT_DIETARY_ATTRIBUTE_LEAK','ALIAS / MORPHOLOGY FAILURE','RETRIEVAL_MISSED_VALID_PRODUCT','COMPATIBILITY_GATE_TOO_STRICT','COMPATIBILITY_GATE_TOO_LOOSE','SCORING / RANKING ERROR','QUERY_NORMALIZATION_ERROR','PRODUCT_NORMALIZATION_ERROR','INVENTORY_METADATA_LIMITATION','MALFORMED / AMBIGUOUS QUERY']
issues=[]
for r in rows:
 if r['review_label'] not in ('WRONG','SHOULD_HAVE_MATCHED','AMBIGUOUS'):continue
 query=describe(r['ingredient_query']); alternatives=json.loads(r['top_3_alternatives'])
 expected=EXPECTED_OVERRIDES.get(r['case_id'],[a['product_id'] for a in alternatives[:1]]) if r['review_label']=='SHOULD_HAVE_MATCHED' else []
 decisions=[compatibility(query,describe(byid[pid]['original_product_name'],feature=byid[pid],product=True)) for pid in expected]
 reasons=sorted({x for d in decisions for x in d.reasons})
 if r['review_label']=='AMBIGUOUS':cause='MALFORMED / AMBIGUOUS QUERY';stage='source ambiguity / metadata uncertainty';rule='Preserve uncertainty; do not invent a gold match.'
 elif r['review_label']=='WRONG':
  old=r['failure_cause']
  cause={'prepared_food_leak':'PREPARED_FOOD_LEAKAGE','wrong_subfamily':'WRONG_SUBFAMILY','wrong_variant':'FLAVOR_ATTRIBUTE_LEAK','wrong_variety':'REQUIRED_VARIANT_DROPPED','wrong_state':'WRONG_FORM_OR_STATE','missing_required_variant':'REQUIRED_VARIANT_DROPPED','wrong_identity':'COMPOUND_NOUN / HEAD_NOUN_COLLISION'}[old]
  stage='ontology extraction / required-attribute gate'
  rule={'PREPARED_FOOD_LEAKAGE':'Resolve composite head before component tokens and combine name/category evidence.', 'WRONG_SUBFAMILY':'Represent distinct vinegar/legume subtypes with directional generic parents.', 'FLAVOR_ATTRIBUTE_LEAK':'Record material flavor/sweetness; reject unrequested flavor on basic foods.', 'REQUIRED_VARIANT_DROPPED':'Preserve modifiers and explicit allowed alternatives in query identity.', 'WRONG_FORM_OR_STATE':'Preserve ripeness/state; recognize composite fruit mix as distinct from single fruit.', 'COMPOUND_NOUN / HEAD_NOUN_COLLISION':'Recognize longest compound identity before component nouns.'}[cause]
 else:
  if query.family=='prepared':cause='COMPATIBILITY_GATE_TOO_STRICT';rule='Recognize legitimate requested purchased composites by their own head/subtype, never by component token.'
  elif query.family is None:cause='ALIAS / MORPHOLOGY FAILURE';rule='Extend reusable food taxonomy and token-level aliases, not full query overrides.'
  elif query.ambiguous or 'form_conflict' in reasons or 'unverified_form' in reasons:cause='QUERY_NORMALIZATION_ERROR';rule='Separate kitchen cutting from purchase form and preserve explicit alternative branches.'
  elif r['case_id']=='968b81f1af81cc16af95':cause='GENERIC_VS_SPECIFIC_ASYMMETRY';rule='No-added-salt can satisfy a lower-sodium request; not the reverse.'
  elif any(x.startswith('unverified_') for x in reasons):cause='INVENTORY_METADATA_LIMITATION';rule='Do not fabricate state evidence; remain abstained if required state is unknown.'
  elif reasons==['verified_food_identity']:cause='RETRIEVAL_MISSED_VALID_PRODUCT';rule='Measure stage-specific recall within structurally compatible family pools.'
  else:cause='COMPATIBILITY_GATE_TOO_STRICT';rule='Use explicit compatibility reasons to repair general purchase/preparation semantics.'
  stage='normalization/identity recognition' if query.family is None else 'compatibility rejected reference product' if any(not d.allowed for d in decisions) else 'ranking/retrieval'
 issues.append({**{k:r[k] for k in ['case_id','ingredient_query','selected_product','review_label','review_notes']},'root_cause':cause,'failure_stage':stage,'before_rejection_reasons':reasons,'reference_product_ids':expected,'reference_product_names':[byid[p]['original_product_name'] for p in expected],'reference_status':'assistant-review diagnostic suggestion, NOT independently verified human gold','general_rule':rule})
material=[r for r in issues if r['review_label']!='AMBIGUOUS']
report={'label_provenance':'assistant review, not independent human QA','labels':dict(collections.Counter(r['review_label'] for r in rows)),'material_case_count':len(material),'root_cause_counts':{c:sum(r['root_cause']==c for r in material) for c in CAUSE_NAMES},'ambiguous_cases':len(issues)-len(material),'random_correct_control_ids':[],'cases':issues}
import random
report['random_correct_control_ids']=[r['case_id'] for r in random.Random(20261008).sample([r for r in rows if r['review_label']=='CORRECT'],30)]
(OUT/'root_causes.json').write_text(json.dumps(report,indent=2)+'\n')
with (OUT/'root_causes.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(issues[0]));writer.writeheader();writer.writerows([{k:json.dumps(v) if isinstance(v,list) else v for k,v in r.items()} for r in issues])
for p in ['Model/product_ontology.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/runtime_artifact_manifest.json']:
 (OUT/(Path(p).name+'.before')).write_bytes((ROOT/p).read_bytes())
(OUT/'before_source_hashes.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['Model/product_ontology.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/runtime_artifact_manifest.json']},indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('cases','random_correct_control_ids')},indent=2))
