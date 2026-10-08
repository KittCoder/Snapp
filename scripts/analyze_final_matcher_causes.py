#!/usr/bin/env python3
"""Freeze assistant-QA diagnoses before the final targeted cleanup."""
import csv,json,hashlib,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService,profile_from_query
from product_ontology import compatibility
OUT=ROOT/'data/matcher_final_cleanup'
def wrong_cause(r):
 q=r['ingredient_query'].lower();p=r['selected_product'].lower()
 if 'cream of tartar' in q:return 'ASSISTANT_LABEL_DISAGREEMENT','Cream of tartar is a baking acid, not dairy cream; matching the named product is structurally correct. Preserve supplied label, adjudicate separately.'
 if 'cream of tartar' in p:return 'COMPOUND_HEAD_COLLISION','Cream of tartar must have its own baking-acid head, distinct from dairy cream.'
 if 'bacon' in q and ('fat' in q or 'drippings' in q):return 'DERIVED_FAT_VS_MEAT','Rendered animal fats/drippings are fats with species/source identity, not meat cuts.'
 if any(w in p for w in ['shortcake','bruschetta','baked beans','lean cuisine']):return 'PREPARED_COMPONENT_LEAKAGE','Composite product heads and entree evidence dominate ingredient modifiers; simple cooked meat remains distinct from an entree.'
 if 'gelatin' in p:return 'GELATIN_DESSERT_VS_BASIC','Plain gelatin powder and flavored ready gelatin dessert require distinct purchased forms.'
 if 'pudding' in q or 'sauce' in q or 'salsa' in q or 'catsup' in q:return 'REQUESTED_DERIVATIVE_HEAD','Preserve purchased sauce, salsa, ketchup and pudding heads on queries as well as products.'
 if 'cereal' in q:return 'SHARED_ALTERNATIVE_HEAD','Shared cereal head scopes over rice/wheat branches; never parse the first component as basic rice.'
 if 'wild rice' in q or 'wine vinegar' in q or 'seasoned' in q:return 'REQUIRED_VARIANT_DROPPED','Named rice/vinegar variants and seasoning remain authoritative; generic products do not satisfy them.'
 if 'pepper' in q:return 'QUANTITY_CONTEXT_NORMALIZATION','Grains/pinches of pepper denote seasoning; whole pepper counts retain vegetable identity.'
 raise ValueError(r)
def main():
 OUT.mkdir(exist_ok=True)
 if (OUT/'root_causes.json').exists():raise ValueError('Frozen diagnoses already exist; do not overwrite after cleanup.')
 files=['Model/product_ontology.py','Model/food_identity_rules.py','Model/product_compatibility.py','Model/product_retrieval.py','Model/runtime_artifact_manifest.json']
 for file in files:(OUT/(Path(file).name+'.before')).write_bytes((ROOT/file).read_bytes())
 (OUT/'source_hashes_before.json').write_text(json.dumps({f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},indent=2))
 for file in ['after_evaluation.json','after_population.jsonl']:(OUT/('before_'+file.removeprefix('after_'))).write_bytes((ROOT/'data/matcher_structural_audit'/file).read_bytes())
 rows=list(csv.DictReader((ROOT/'data/matcher_structural_holdout/structural_holdout_assistant_labeled.csv').open()));service=ProductMatchService();cases=[]
 for r in rows:
  if r['review_label'] not in ('WRONG','SHOULD_HAVE_MATCHED'):continue
  q,_=profile_from_query(r['ingredient_query'],service.overrides);alts=json.loads(r['top_3_alternatives']);refs=[]
  for alt in alts:
   pid=alt.get('product_id');identity=service.identity_catalog.identities.get(pid)
   if identity:refs.append({'product_id':pid,'product_name':alt.get('product_name'),'gate_reasons':list(compatibility(q.ontology,identity).reasons),'ontology':identity.to_dict()})
  if r['review_label']=='WRONG':cause,rule=wrong_cause(r);stage='B ontology parsing / D compatibility gate'
  else:
   reasons=json.loads(r['reason_codes']);stage='B ontology parsing' if 'unknown_family' in reasons or 'ambiguous_identity_or_variant' in reasons else 'D compatibility gate' if 'no_inventory_with_verified_required_identity' in reasons else 'E scoring / F threshold'
   cause='MISSING_PURCHASED_HEAD_OR_ALIAS' if stage.startswith('B') or q.ontology.family=='prepared' else 'REQUIRED_METADATA_OR_FORM_GATE'
   rule='Add genuine taxonomy/alias facts and supported preparation directions; keep unknown purchased attributes unverified.'
  cases.append({**r,'root_cause':cause,'general_rule':rule,'failure_stage':stage,'before_query_ontology':q.ontology.to_dict(),'diagnostic_reference_candidates':refs})
 assert sum(r['review_label']=='WRONG' for r in cases)==28 and sum(r['review_label']=='SHOULD_HAVE_MATCHED' for r in cases)==40
 report={'provenance':'assistant labels, not independent human certification','counts':dict(collections.Counter(r['review_label'] for r in rows)),'wrong_root_cause_counts':dict(collections.Counter(r['root_cause'] for r in cases if r['review_label']=='WRONG')),'cases':cases}
 (OUT/'root_causes.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
if __name__=='__main__':main()
